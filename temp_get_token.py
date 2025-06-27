import requests

admin_user = {
	'name': 'Admin User',
	'email': 'admin@example.com',
	'password': 'password'
}

# Register the admin user
requests.post('http://localhost:8080/api/v1/auths/signup', json=admin_user)

# Login and get the token
session = requests.Session()
session.post('http://localhost:8080/auth', data=admin_user)
token = session.cookies.get('token')

print(f'Token: {token}')