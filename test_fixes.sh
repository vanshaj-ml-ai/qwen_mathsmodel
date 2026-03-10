#!/bin/bash
# Test script to verify non-determinism fix

echo "🧪 Non-Determinism Fix Verification"
echo "===================================="
echo ""

# Kill existing server if running
echo "📍 Step 1: Stopping existing server..."
pkill -f "uvicorn.*app.py" 2>/dev/null
sleep 2
echo "✓ Server stopped"
echo ""

# Start fresh server
echo "📍 Step 2: Starting fresh server on port 8001..."
cd /home/ec2-user/tanishk/rdsharma-rag
source .venv/bin/activate
python3 -m uvicorn backend.app:app --host 0.0.0.0 --port 8001 > /tmp/server.log 2>&1 &
SERVER_PID=$!
echo "✓ Server started (PID: $SERVER_PID)"
sleep 3
echo ""

# Test if server is running
echo "📍 Step 3: Testing server health..."
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health)
if [ "$HEALTH" = "200" ]; then
    echo "✓ Server is healthy (HTTP 200)"
else
    echo "✗ Server health check failed (HTTP $HEALTH)"
    echo "Server logs:"
    tail -20 /tmp/server.log
    exit 1
fi
echo ""

# Test #1: Same question multiple times
echo "📍 Step 4: Test #1 - Same question 3 times (should get identical answers from cache)..."
echo ""

QUESTION="Find the distance between points A(2,3) and B(5,7)"

for i in 1 2 3; do
    echo "  Request $i:"
    RESPONSE=$(curl -s -X POST http://localhost:8001/chat/text \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "question=$QUESTION" 2>/dev/null)
    
    # Extract distance value
    DISTANCE=$(echo "$RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('solution', {}).get('values', {}).get('distance', 'N/A'))" 2>/dev/null)
    VERIFIED=$(echo "$RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('verified', False))" 2>/dev/null)
    
    echo "    Distance: $DISTANCE"
    echo "    Verified: $VERIFIED"
done

echo ""
echo "✓ Test #1 Complete - If all 3 distances are the same, cache is working!"
echo ""

# Test #2: Similar but different questions
echo "📍 Step 5: Test #2 - Different questions (should get different correct answers)..."
echo ""

QUESTIONS=(
    "Find the distance between points A(0,0) and B(3,4)"
    "Find the distance between points A(0,0) and B(6,8)"
    "Find the distance between points A(1,1) and B(4,5)"
)

for q in "${QUESTIONS[@]}"; do
    echo "  Question: $q"
    RESPONSE=$(curl -s -X POST http://localhost:8001/chat/text \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "question=$q" 2>/dev/null)
    
    DISTANCE=$(echo "$RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('solution', {}).get('values', {}).get('distance', 'N/A'))" 2>/dev/null)
    echo "    Answer: $DISTANCE"
done

echo ""
echo "✓ Test #2 Complete"
echo ""

# Final summary
echo "════════════════════════════════════════"
echo "🎉 VERIFICATION COMPLETE!"
echo "════════════════════════════════════════"
echo ""
echo "What to check:"
echo "  ✓ Test #1: All 3 distances identical = Cache working"
echo "  ✓ Test #2: Different questions get different answers = LLM deterministic"
echo "  ✓ Verified=true for all = Validation passing"
echo ""
echo "Server is running on http://localhost:8001"
echo "Logs: tail -f /tmp/server.log"
echo ""
