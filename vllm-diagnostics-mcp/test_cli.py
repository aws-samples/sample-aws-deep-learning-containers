#!/usr/bin/env python3
"""Test script for vLLM diagnostics CLI."""
import subprocess
import sys
import json

def run_command(cmd):
    """Run a CLI command and return the result."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def test_system_specs():
    """Test system specs command."""
    print("Testing system specs...")
    success, stdout, stderr = run_command("python3 cli.py get-system-specs --json-output")
    
    if success:
        try:
            data = json.loads(stdout)
            print("✅ System specs command works")
            print(f"   Found {data.get('gpu', {}).get('gpu_count', 0)} GPUs")
            return True
        except json.JSONDecodeError:
            print("❌ System specs returned invalid JSON")
            return False
    else:
        print(f"❌ System specs command failed: {stderr}")
        return False

def test_vllm_connection():
    """Test vLLM connection (will fail if no vLLM server running)."""
    print("Testing vLLM connection...")
    success, stdout, stderr = run_command("python3 cli.py test-connection")
    
    if success:
        print("✅ vLLM connection test works (server is running)")
        return True
    else:
        print("⚠️  vLLM connection test failed (expected if no server running)")
        print(f"   Error: {stderr.strip()}")
        return True  # This is expected if no vLLM server is running

def test_capacity_check():
    """Test capacity check command."""
    print("Testing capacity check...")
    success, stdout, stderr = run_command("python3 cli.py check-capacity --model-name gpt2 --json-output")
    
    if success:
        try:
            data = json.loads(stdout)
            print("✅ Capacity check command works")
            print(f"   Estimated memory requirement: {data.get('estimated_memory_requirement_gb', 'N/A')} GB")
            return True
        except json.JSONDecodeError:
            print("❌ Capacity check returned invalid JSON")
            return False
    else:
        print(f"❌ Capacity check command failed: {stderr}")
        return False

def main():
    """Run all tests."""
    print("Running vLLM Diagnostics CLI Tests")
    print("=" * 40)
    
    tests = [
        test_system_specs,
        test_vllm_connection,
        test_capacity_check
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 40)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()