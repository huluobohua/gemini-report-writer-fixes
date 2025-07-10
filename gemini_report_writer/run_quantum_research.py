#!/usr/bin/env python3
"""
Simple script to run the quantum computing research with better visibility.
"""
import sys
import time
from main import ReportWorkflow

def main():
    print("Starting Quantum Computing Research Report Generation...")
    print("=" * 60)
    
    try:
        workflow = ReportWorkflow()
        
        print("Initializing report generation for: 'quantum computing advancements 2020-2025'")
        start_time = time.time()
        
        # Run the workflow
        report = workflow.run("quantum computing advancements 2020-2025")
        
        end_time = time.time()
        duration = end_time - start_time
        
        print("=" * 60)
        print(f"Report generation completed successfully in {duration:.2f} seconds!")
        print("=" * 60)
        
        return report
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        return None
    except Exception as e:
        print(f"\nError occurred: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = main()
    if result:
        print("\nFinal report preview (first 500 characters):")
        print("-" * 50)
        print(result[:500])
        print("...")
        print("-" * 50)
    else:
        print("No report generated.")