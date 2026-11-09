import sys
from PIL import Image
from usreport.extract import extract
from usreport.schema import SLOTS
img = Image.open(sys.argv[1]); print(img.size)
r = extract(img)
print('psm', r['psm'])
for s in SLOTS:
    iss = '; '.join(i['level'] + ': ' + i['msg'] for i in r['issues'].get(s.letter, []))
    print(f"{s.letter} {s.label:28} {str(r['values'][s.key]):>8}   {iss}")
print('LINES:'); [print('  ', l) for l in r['lines']]
