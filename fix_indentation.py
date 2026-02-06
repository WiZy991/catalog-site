# Fix indentation in services.py line 371
with open('catalog/services.py', 'rb') as f:
    content = f.read()

# Convert to string and split into lines
try:
    lines = content.decode('utf-8').splitlines(True)
except:
    lines = content.decode('latin-1').splitlines(True)

# Fix line 371 (index 370) - ensure it has exactly 8 spaces
if len(lines) > 370:
    line = lines[370]
    # Remove all leading whitespace and add exactly 8 spaces
    stripped = line.lstrip()
    if stripped.startswith('if not result'):
        lines[370] = '        ' + stripped

# Write back
with open('catalog/services.py', 'wb') as f:
    content = ''.join(lines)
    f.write(content.encode('utf-8'))

print('Fixed indentation on line 371')
