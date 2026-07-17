import requests
import random
import sys

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("Starting Auth Layer Tests...")
    
    # Generate a unique email for this test run
    random_id = random.randint(1000, 9999)
    email = f"shop_{random_id}@test.com"
    password = "supersecretpassword123"
    shop_name = f"Test Shop {random_id}"

    # 1. Sign Up
    print("\n--- 1. Testing Signup ---")
    payload = {
        "shop_name": shop_name,
        "email": email,
        "password": password
    }
    response = requests.post(f"{BASE_URL}/auth/signup", json=payload)
    print(f"Signup response status: {response.status_code}")
    print(f"Signup response body: {response.json()}")
    assert response.status_code == 200, "Signup failed"
    token_data = response.json()
    assert "access_token" in token_data, "Token not found in signup response"
    token = token_data["access_token"]
    print("Signup testing passed.")

    # 2. Duplicate Signup
    print("\n--- 2. Testing Duplicate Signup ---")
    response = requests.post(f"{BASE_URL}/auth/signup", json=payload)
    print(f"Duplicate Signup response status: {response.status_code}")
    print(f"Duplicate Signup response body: {response.json()}")
    assert response.status_code == 400, "Duplicate signup did not fail with 400"
    print("Duplicate signup testing passed.")

    # 3. Log In (Success)
    print("\n--- 3. Testing Login (Success) ---")
    login_payload = {
        "email": email,
        "password": password
    }
    response = requests.post(f"{BASE_URL}/auth/login", json=login_payload)
    print(f"Login success status: {response.status_code}")
    print(f"Login success body: {response.json()}")
    assert response.status_code == 200, "Login failed"
    login_token_data = response.json()
    assert "access_token" in login_token_data, "Token not found in login response"
    print("Login success testing passed.")

    # 4. Log In (Failure)
    print("\n--- 4. Testing Login (Failure) ---")
    login_fail_payload = {
        "email": email,
        "password": "wrong_password"
    }
    response = requests.post(f"{BASE_URL}/auth/login", json=login_fail_payload)
    print(f"Login failure status: {response.status_code}")
    print(f"Login failure body: {response.json()}")
    assert response.status_code == 401, "Login with wrong password did not fail with 401"
    print("Login failure testing passed.")

    # 5. Access Protected Route (Success)
    print("\n--- 5. Testing Access Protected Route (Success) ---")
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print(f"Protected route status: {response.status_code}")
    print(f"Protected route body: {response.json()}")
    assert response.status_code == 200, "Accessing protected route failed"
    user_data = response.json()
    assert user_data["email"] == email, "Email in protected route does not match"
    assert user_data["shop_name"] == shop_name, "Shop name does not match"
    print("Access protected route (Success) testing passed.")

    # 6. Access Protected Route (Missing Token)
    print("\n--- 6. Testing Access Protected Route (Missing Token) ---")
    response = requests.get(f"{BASE_URL}/auth/me")
    print(f"Protected route (no token) status: {response.status_code}")
    print(f"Protected route (no token) body: {response.json()}")
    assert response.status_code == 401, "Accessing protected route without token did not fail with 401"
    print("Access protected route (Missing Token) testing passed.")

    # 7. Access Protected Route (Invalid Token)
    print("\n--- 7. Testing Access Protected Route (Invalid Token) ---")
    headers_invalid = {
        "Authorization": "Bearer invalidtoken123"
    }
    response = requests.get(f"{BASE_URL}/auth/me", headers=headers_invalid)
    print(f"Protected route (invalid token) status: {response.status_code}")
    print(f"Protected route (invalid token) body: {response.json()}")
    assert response.status_code == 401, "Accessing protected route with invalid token did not fail with 401"
    print("Access protected route (Invalid Token) testing passed.")

    print("\nALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\nTEST FAILURE: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error during test execution: {e}")
        sys.exit(1)
