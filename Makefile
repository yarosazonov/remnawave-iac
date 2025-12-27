deploy:
	.venv/bin/python orchestration/deploy.py

deploy-reboot:
	.venv/bin/python orchestration/deploy.py reboot

deploy-apply:
	.venv/bin/python orchestration/deploy.py apply

deploy-destroy:
	.venv/bin/python orchestration/deploy.py destroy
