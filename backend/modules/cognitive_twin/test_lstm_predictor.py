"""
test_lstm_predictor.py — predictor ka dry-run test
State mirror se kuch data hona chahiye SQLite mein
"""
import asyncio, sys
sys.path.insert(0, ".")
from backend.modules.cognitive_twin.lstm_predictor import get_predictor

async def main():
    print("=== LSTM Predictor Test ===\n")
    predictor = get_predictor()
    count = await predictor.run_and_store()
    print(f"\nAlerts generated: {count}")
    print("\n✅ Test complete")

asyncio.run(main())
