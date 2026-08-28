import requests

url = "https://irctc1.p.rapidapi.com/api/v1/searchStation"

querystring = {"query":"BJU"}

headers = {
	"x-rapidapi-key": "3454850435mshbb3b696f36c3166p1904d0jsnd3a9fc6bab83",
	"x-rapidapi-host": "irctc1.p.rapidapi.com"
}

response = requests.get(url, headers=headers, params=querystring)

print(response.json())