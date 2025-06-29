# Basic endpoints

curl -s <http://localhost:8000/> | jq
curl -s <http://localhost:8000/health> | jq  
curl -s <http://localhost:8000/info> | jq

# Health checks

curl -s <http://localhost:8000/health/db> | jq
curl -s <http://localhost:8000/health/redis> | jq

# Documentation endpoints

curl -s <http://localhost:8000/docs>
curl -s <http://localhost:8000/openapi.json> | jq

# Performance timing

curl -w "Total time: %{time_total}s\n" -o /dev/null -s <http://localhost:8000/health>
