import time
from pathlib import Path
log_file = Path(".idx/last_build.log")
log_file.parent.mkdir(exist_ok=True)
print("🛡️ TradeShield AI Bridge Active. Monitoring .idx/last_build.log...")
while True:
    if log_file.exists():
        with log_file.open("r") as f:
            pass 
    time.sleep(1)
