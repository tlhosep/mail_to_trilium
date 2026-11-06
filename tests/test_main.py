import unittest
from src.main import extract_target_folder

class TestEmailToTrilium(unittest.TestCase):
    
    def test_extract_target_folder_found(self):
        subject = "Wichtige Dokumente [target:Finanzen]"
        folder = extract_target_folder(subject)
        self.assertEqual(folder, "Finanzen")
        
    def test_extract_target_folder_not_found(self):
        subject = "Normale E-Mail ohne Target"
        folder = extract_target_folder(subject)
        self.assertIsNone(folder)

    def test_extract_target_folder_with_spaces(self):
        subject = "Rezept [target: Kochen & Backen ]"
        folder = extract_target_folder(subject)
        self.assertEqual(folder, "Kochen & Backen")

if __name__ == '__main__':
    unittest.main()
