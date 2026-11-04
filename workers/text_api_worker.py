"""Bounded text API request, run under the existing cancellable job process runner."""
import json
import sys
import urllib.error
import urllib.request

def main():
    with open(sys.argv[1], encoding="utf-8") as stream:
        request = json.load(stream)
    call = urllib.request.Request(request["url"], data=json.dumps(request["body"]).encode(),
                                  headers=request["headers"])
    try:
        with urllib.request.urlopen(call, timeout=request["timeout"]) as response:
            data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("response too large")
        payload = json.loads(data)
        text = payload["choices"][0]["message"]["content"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("empty response")
        print(json.dumps({"text": text.strip()}, ensure_ascii=False))
    except urllib.error.HTTPError as error:
        print(json.dumps({"error": "模型 API 返回 HTTP {}".format(error.code)}))
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        print(json.dumps({"error": "模型 API 连接失败或返回格式无效，请检查地址、模型和密钥"}))

if __name__ == "__main__":
    main()
