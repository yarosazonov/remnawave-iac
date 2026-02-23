@echo off
TITLE Monitoring tunnel
echo ------------------------------------------------
echo Opening Tunnel...
echo prometheus is accessible at: http://localhost:9092
echo grafana is accessible at: http://localhost:9093
echo ------------------------------------------------

:: The -N flag tells SSH to just forward ports and not open a shell.
ssh -L 9092:localhost:9090 -L 9093:localhost:3000 <user>@<address> -N

:: The lines below only run if the connection fails or you close it.
echo.
echo ------------------------------------------------
echo ❌ The tunnel has closed.
echo ------------------------------------------------
pause
