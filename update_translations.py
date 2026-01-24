#!/usr/bin/env python
"""
Automated Translation Updater
Updates Django .po files with new translations from translation_updates.txt
"""

import os
import re
from pathlib import Path

def update_po_file(po_path, translations, lang_code):
    """Update a single .po file with new translations"""
    
    print(f"\nUpdating {po_path} for language: {lang_code}")
    
    # Read existing .po file
    with open(po_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Track what we added
    added_count = 0
    updated_count = 0
    
    # Process each translation
    for key, values in translations.items():
        en_text = values['en']
        target_text = values[lang_code]
        
        # Check if this msgid already exists
        pattern = rf'msgid "{re.escape(key)}"'
        if re.search(pattern, content):
            # Update existing entry
            old_pattern = rf'(msgid "{re.escape(key)}"\nmsgstr )"[^"]*"'
            new_replacement = rf'\1"{target_text}"'
            new_content = re.sub(old_pattern, new_replacement, content)
            if new_content != content:
                content = new_content
                updated_count += 1
                print(f"  ✓ Updated: {key}")
        else:
            # Add new entry at the end
            new_entry = f'\nmsgid "{key}"\nmsgstr "{target_text}"\n'
            content += new_entry
            added_count += 1
            print(f"  + Added: {key}")
    
    # Write updated content
    with open(po_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  Summary: {added_count} added, {updated_count} updated")
    return added_count, updated_count

def parse_translations(txt_file):
    """Parse translation_updates.txt file"""
    translations = {}
    
    with open(txt_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Parse format: key|en|ru|uz
            parts = line.split('|')
            if len(parts) == 4:
                key, en, ru, uz = parts
                translations[key] = {
                    'en': en,
                    'ru': ru,
                    'uz': uz
                }
    
    return translations

def main():
    # Get project root
    script_dir = Path(__file__).parent
    
    # Parse translations
    txt_file = script_dir / 'translation_updates.txt'
    if not txt_file.exists():
        print(f"Error: {txt_file} not found!")
        return
    
    print(f"Parsing translations from {txt_file}...")
    translations = parse_translations(txt_file)
    print(f"Found {len(translations)} translation keys")
    
    # Update each language
    locale_dir = script_dir / 'locale'
    languages = ['en', 'ru', 'uz']
    
    total_added = 0
    total_updated = 0
    
    for lang in languages:
        po_file = locale_dir / lang / 'LC_MESSAGES' / 'django.po'
        if po_file.exists():
            added, updated = update_po_file(po_file, translations, lang)
            total_added += added
            total_updated += updated
        else:
            print(f"Warning: {po_file} not found, skipping...")
    
    print(f"\n{'='*60}")
    print(f"TOTAL: {total_added} translations added, {total_updated} updated")
    print(f"{'='*60}")
    print(f"\nNext step: Run 'python manage.py compilemessages' to compile translations")

if __name__ == '__main__':
    main()
