import os
import imaplib
import smtplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
import re
import time
import requests
from dotenv import load_dotenv

# Lokale .env laden (wichtig für VS-Code)
load_dotenv()

# Konfiguration laden
IMAP_SERVER = os.getenv("IMAP_SERVER")
IMAP_PORT = int(os.getenv("IMAP_PORT", 993))
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))

TRILIUM_URL = os.getenv("TRILIUM_URL", "").rstrip("/")
TRILIUM_TOKEN = os.getenv("TRILIUM_ETAPI_TOKEN")
DEFAULT_FOLDER_NAME = os.getenv("TRILIUM_DEFAULT_FOLDER_NAME", "E-Mails")
DEFAULT_FOLDER_ID = os.getenv("TRILIUM_DEFAULT_FOLDER_ID")
ERROR_EMAIL = os.getenv("ERROR_NOTIFICATION_EMAIL")

# VORHER:
# headers = {
#     "Authorization": TRILIUM_TOKEN,
#     "Content-Type": "application/json"
# }

# NACHHER (KORRIGIERT):
headers = {
    "Authorization": f"Bearer {TRILIUM_TOKEN}",
    "Content-Type": "application/json"
}


def log(message):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)

def send_error_email(subject, error_msg):
    log(f"Sende Fehler-E-Mail: {subject}")
    if not ERROR_EMAIL:
        return
    try:
        msg = MIMEText(f"In email_to_trilium ist ein Fehler aufgetreten:\n\n{error_msg}")
        msg['Subject'] = f"[email_to_trilium] {subject}"
        msg['From'] = IMAP_USER
        msg['To'] = ERROR_EMAIL

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(IMAP_USER, IMAP_PASSWORD)
            server.sendmail(IMAP_USER, ERROR_EMAIL, msg.as_string())
    except Exception as e:
        log(f"Kritischer Fehler: Konnte Fehler-E-Mail nicht senden: {e}")

def decode_mime_words(s):
    if not s:
        return ""
    parts = decode_header(s)
    return "".join(
        brand.decode(encoding or 'utf-8') if isinstance(brand, bytes) else brand
        for brand, encoding in parts
    )

def extract_target_folder(subject):
    # Sucht nach [target:Ordnername]
    match = re.search(r'\[target:(.+?)\]', subject)
    if match:
        return match.group(1).strip()
    return None

def get_or_create_folder(folder_name, parent_id="root"):
    # Die robusteste Trilium-Syntax für die gezielte Titelsuche
    search_query = f'note.title="{folder_name}"'
    log(f"Suche nach bestehendem Ordner mit Query: {search_query}")
    
    res = requests.get(
        f"{TRILIUM_URL}/etapi/notes", 
        headers=headers, 
        params={"search": search_query}
    )
    
    if res.status_code == 200:
        results = res.json().get("results", [])
        # Wir gehen die Ergebnisse durch und suchen den exakten Treffer
        for note in results:
            if note.get("title") == folder_name and note.get("type") == "text":
                log(f"Ordner '{folder_name}' erfolgreich gefunden (ID: {note['noteId']})")
                return note["noteId"]
                
    # Wenn die API nichts liefert, legen wir den Ordner neu an
    log(f"Ordner '{folder_name}' wurde in Trilium nicht gefunden. Erstelle neu...")
    payload = {
        "parentNoteId": parent_id,
        "type": "text",
        "title": folder_name,
        "isProtected": False
    }
    create_res = requests.post(f"{TRILIUM_URL}/etapi/create-note", headers=headers, json=payload)
    if create_res.status_code in [200, 201]:
        return create_res.json()["note"]["noteId"]
    else:
        raise Exception(f"Konnte Ordner '{folder_name}' nicht erstellen: {create_res.text}")

def create_trilium_note(parent_id, title, content_html, attachments):
    # Hauptnotiz erstellen (Korrektur: isProtected entfernt)
    payload = {
        "parentNoteId": parent_id,
        "type": "text",
        "title": title,
        "content": content_html
    }
    res = requests.post(f"{TRILIUM_URL}/etapi/create-note", headers=headers, json=payload)
    if res.status_code not in [200,201]:
        raise Exception(f"Fehler beim Erstellen der Notiz: {res.text}")
    
    note_id = res.json()["note"]["noteId"]
    
    # Anhänge als Child-Notes hochladen
    for filename, content_bytes in attachments:
        log(f"Lade Anhang hoch: {filename}")
        file_payload = {
            "parentNoteId": note_id,
            "type": "file",
            "title": filename
        }
        # Datei-Notiz-Hülle erstellen
        file_res = requests.post(f"{TRILIUM_URL}/etapi/create-note", headers=headers, json=file_payload)
        if file_res.status_code in [200,201]:
            file_note_id = file_res.json()["note"]["noteId"]
            # Inhalt hochladen via PUT
            requests.put(
                f"{TRILIUM_URL}/etapi/notes/{file_note_id}/content", 
                headers={"Authorization": f"Bearer {TRILIUM_TOKEN}", "Content-Type": "application/octet-stream"}, 
                data=content_bytes
            )
    return note_id

def process_email(msg_bytes):
    msg = email.message_from_bytes(msg_bytes)
    subject = decode_mime_words(msg.get("Subject", "Kein Betreff"))
    sender = decode_mime_words(msg.get("From", "Unbekannt"))
    date_str = msg.get("Date", "Unbekanntes Datum")
    
    log(f"Verarbeite E-Mail: {subject}")
    
    body_html = ""
    body_text = ""
    attachments = []
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            if "attachment" in content_disposition:
                filename = decode_mime_words(part.get_filename())
                if filename:
                    attachments.append((filename, part.get_payload(decode=True)))
            elif content_type == "text/html":
                body_html = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
            elif content_type == "text/plain":
                body_text = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='ignore')
        if content_type == "text/html":
            body_html = payload
        else:
            body_text = payload

    # HTML-Formatierung erzwingen
    if not body_html:
        body_html = f"<pre>{body_text}</pre>"
        
    header_info = f"<div style='background:#f3f3f3; padding:10px; margin-bottom:15px; border-left:4px solid #0076d6;'>" \
                  f"<b>Von:</b> {sender}<br><b>Datum:</b> {date_str}</div>"
    full_content = header_info + body_html

    # Zielordner bestimmen
    target_name = extract_target_folder(subject)
    if target_name:
        parent_id = get_or_create_folder(target_name)
    elif DEFAULT_FOLDER_ID:
        parent_id = DEFAULT_FOLDER_ID
    else:
        parent_id = get_or_create_folder(DEFAULT_FOLDER_NAME)

    create_trilium_note(parent_id, subject, full_content, attachments)

def check_mail():
    log("Prüfe Posteingang...")
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASSWORD)
        mail.select("inbox")
        
        # Alle ungelesenen Nachrichten holen (oder einfach alle, da wir löschen/verschieben)
        status, data = mail.search(None, "ALL")
        mail_ids = data[0].split()
        
        log(f"{len(mail_ids)} E-Mails im Posteingang gefunden.")
        
        for m_id in mail_ids:
            status, msg_data = mail.fetch(m_id, "(RFC822)")
            msg_bytes = msg_data[0][1]
            
            try:
                process_email(msg_bytes)
                # Erfolgreich -> Löschen
                mail.store(m_id, '+FLAGS', '\\Deleted')
                log("E-Mail erfolgreich verarbeitet und zum Löschen markiert.")
            except Exception as inner_e:
                error_context = f"Fehler bei Mail-ID {m_id.decode()}: {str(inner_e)}"
                log(error_context)
                send_error_email("Import fehlgeschlagen", error_context)
                
                # In Ordner "Fehler" verschieben (Ordner erstellen falls nicht da)
                mail.create("Fehler")
                mail.copy(m_id, "Fehler")
                mail.store(m_id, '+FLAGS', '\\Deleted')
                log("E-Mail wegen Fehlers in den Ordner 'Fehler' verschoben.")
        
        mail.expunge()
        mail.logout()
    except Exception as e:
        log(f"Allgemeiner IMAP-Fehler: {e}")
        send_error_email("Verbindungsfehler", str(e))

if __name__ == "__main__":
    # Wenn im Docker-Modus, läuft die Schleife unendlich alle 5 Minuten
    if os.getenv("DOCKER_MODE") == "true":
        log("Anwendung im Docker-Modus gestartet (Intervall: 5 Minuten).")
        while True:
            check_mail()
            time.sleep(300)
    else:
        # Lokaler Einzeldurchlauf für VS-Code Tests
        log("Anwendung im lokalen Einzelmodus gestartet.")
        check_mail()
