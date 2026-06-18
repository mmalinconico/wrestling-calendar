import requests

url = "https://en.wikipedia.org/wiki/List_of_WWE_pay-per-view_and_livestreaming_supercards"

response = requests.get(url)

print(response.status_code)
print(response.text[:500])
