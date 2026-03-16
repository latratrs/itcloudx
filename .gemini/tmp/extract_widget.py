import os

path = os.path.expanduser('~/itcloudx/astrowind/src/pages/index.astro')
audit_path = os.path.expanduser('~/itcloudx/astrowind/src/pages/audit.astro')

with open(path) as f:
    index = f.read()
with open(audit_path) as f:
    audit = f.read()

# Extract audit widget HTML (from screen-upload div to end of screen-error div)
widget_start = audit.find('<div id="screen-upload"')
widget_end = audit.find('</div>', audit.find('<div id="screen-error"')) + len('</div>')
audit_widget = audit[widget_start:widget_end]
print(f"Audit widget: {len(audit_widget)} bytes")
print("Starts:", audit_widget[:80])
print("Ends:", audit_widget[-80:])

# Find homepage widget to replace (from scan-widget div content)
hw_start = index.find('<div id="state-upload"')
hw_end = index.find('<!-- Trust strip')
print(f"\nHomepage widget to replace: chars {hw_start} to {hw_end}")
print("HP starts:", index[hw_start:hw_start+80])
