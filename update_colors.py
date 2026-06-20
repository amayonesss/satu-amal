import os

directory = r"C:\Users\Elitebook\satu-amal\templates"

replacements = {
    '#1a4f8a': '#1f59d2',
    '#0d3870': '#1646ad',
    '#0d2f5e': '#0f3d99',
    '#1e5a9e': '#2e73f2',
    'rgba(26,79,138': 'rgba(31,89,210'
}

for root, _, files in os.walk(directory):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = content
            for old, new in replacements.items():
                new_content = new_content.replace(old, new)
            
            if new_content != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Updated {filepath}")
