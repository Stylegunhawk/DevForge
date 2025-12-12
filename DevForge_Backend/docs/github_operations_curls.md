curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user | jq .

curl -s -H "Authorization: token $GITHUB_TOKEN" "https://api.github.com/user/repos?per_page=100" | jq .
