import json, subprocess, time
from app.agent import run_agent

scenarios = json.load(open("evals/scenarios.json"))
passed = 0

for s in scenarios:
    subprocess.run(s["break"], shell=True)                       # break
    for i in range(5):
        subprocess.run("curl -s -o /dev/null -X POST localhost:8080/orders", shell=True)   # traffic
    try:
        report = run_agent(s["alert"])
        ok = report.root_cause_service == s["expected_root_cause_service"]
                                                 
        print(s["name"], "PASS" if ok else "FAIL", report.root_cause_service)
        if ok:
            passed += 1
    except Exception as e:
        print(s["name"], "ERROR", e)

    finally:
        subprocess.run(s["fix"], shell=True)                     # always fix
        time.sleep(130)

print(f"Score: {passed}/{len(scenarios)}")
