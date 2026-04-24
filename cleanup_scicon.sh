#!/bin/bash
echo "Sci-CON Slack queue クリーンアップ中..."
ssh -i ~/.ssh/id_ed25519 user@100.111.32.35 \
  "python3 -c \"
import sqlite3, datetime
c = sqlite3.connect('/Users/user/iris_slack_queue.db')
n = c.execute(\\\"UPDATE slack_events SET status='done' WHERE channel='C01TJ43N0JE' AND status IN ('pending','claimed')\\\").rowcount
c.commit()
print(f'Sci-CON分 {n}件をdone済みにしました')
c.close()
\""
