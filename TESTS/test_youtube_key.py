import requests

API_KEY = "YOUTUBE_API_KEY"
VIDEO_ID = "dQw4w9WgXcQ"  # Rickroll for testing

def test_youtube_api():
    url = f"https://www.googleapis.com/youtube/v3/videos?id={VIDEO_ID}&key={API_KEY}&part=snippet,statistics"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if "items" in data and len(data["items"]) > 0:
            video = data["items"][0]
            print(f"SUCCESS! Title: {video['snippet']['title']}")
        else:
            print("FAILURE: No video found or key restricted.")
            print(data)
    else:
        print(f"FAILURE: Status code {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_youtube_api()
