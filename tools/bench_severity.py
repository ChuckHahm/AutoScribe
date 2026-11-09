from usreport.server import benchmark
print(f"{'photo':6}{'unit':5}{'sev':>5}  {'field acc':>9}  {'fully ok':>8}  {'wrong&flag':>10}  {'wrong&SILENT':>12}")
for photo, sevs in ((False, [1.0]), (True, [0.3, 0.6, 1.0])):
    for unit in ('mm', 'cm'):
        for sev in sevs:
            r = benchmark(n=20, photo=photo, unit=unit, severity=sev)
            print(f"{str(photo):6}{unit:5}{sev:5.1f}  {r['field_accuracy']*100:8.1f}%  {r['reports_fully_correct']:>8}  {r['wrong_and_flagged']:>10}  {r['wrong_and_silent']:>12}")
