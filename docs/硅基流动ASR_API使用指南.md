# 硅基流动 ASR API 使用指南

## 基本信息

| 项目 | 说明 |
|------|------|
| API地址 | `https://api.siliconflow.cn/v1/audio/transcriptions` |
| 请求方式 | POST (multipart/form-data) |
| 认证方式 | Bearer Token |

## 支持模型

| 模型名称 | 说明 |
|----------|------|
| `TeleAI/TeleSpeechASR` | 电信AI语音识别 |
| `FunAudioLLM/SenseVoiceSmall` | 感知语音小模型 |

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | file | 是 | 音频文件对象，时长不超过1小时，大小不超过50MB |
| `model` | string | 是 | 模型名称 |

## 认证方式

在请求头中添加 Authorization：
```
Authorization: Bearer YOUR_API_KEY
```

## 使用示例

### cURL 调用

```bash
curl -X POST "https://api.siliconflow.cn/v1/audio/transcriptions" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@/path/to/audio.wav" \
  -F "model=TeleAI/TeleSpeechASR"
```

### Python 调用

```python
import requests

API_KEY = "YOUR_API_KEY"
API_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
MODEL = "TeleAI/TeleSpeechASR"

def transcribe_audio(audio_path: str) -> str:
    """
    调用硅基流动ASR API进行语音转文字

    Args:
        audio_path: 音频文件路径

    Returns:
        转写文本
    """
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    with open(audio_path, "rb") as audio_file:
        files = {
            "file": audio_file
        }
        data = {
            "model": MODEL
        }

        response = requests.post(API_URL, headers=headers, files=files, data=data)

        if response.status_code == 200:
            result = response.json()
            return result.get("text", "")
        else:
            raise Exception(f"API请求失败: {response.status_code} - {response.text}")

# 使用示例
if __name__ == "__main__":
    text = transcribe_audio("123.wav")
    print(f"转写结果: {text}")
```

### Python 异步调用

```python
import aiohttp
import asyncio

API_KEY = "YOUR_API_KEY"
API_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
MODEL = "TeleAI/TeleSpeechASR"

async def transcribe_audio_async(audio_path: str) -> str:
    """
    异步调用硅基流动ASR API

    Args:
        audio_path: 音频文件路径

    Returns:
        转写文本
    """
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    with open(audio_path, "rb") as audio_file:
        audio_data = audio_file.read()

    data = aiohttp.FormData()
    data.add_field("file", audio_data, filename=audio_path, content_type="audio/wav")
    data.add_field("model", MODEL)

    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, headers=headers, data=data) as response:
            if response.status == 200:
                result = await response.json()
                return result.get("text", "")
            else:
                error_text = await response.text()
                raise Exception(f"API请求失败: {response.status} - {error_text}")

# 使用示例
if __name__ == "__main__":
    text = asyncio.run(transcribe_audio_async("123.wav"))
    print(f"转写结果: {text}")
```

## 响应格式

### 成功响应

```json
{
    "text": "转写的文本内容"
}
```

响应头包含 `x-siliconcloud-trace-id`，可用于日志查询和问题排查。

### 错误响应

常见错误码：
| 状态码 | 说明 |
|--------|------|
| 401 | 认证失败，API Key无效 |
| 400 | 参数错误，文件格式不支持等 |
| 500 | 服务端错误 |

## 文件限制

- 音频时长：不超过1小时
- 文件大小：不超过50MB
- 支持格式：wav、mp3等常见音频格式

## 测试记录

### 测试样例：123.wav

```bash
curl -X POST "https://api.siliconflow.cn/v1/audio/transcriptions" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@123.wav" \
  -F "model=TeleAI/TeleSpeechASR"
```

**返回结果：**
```json
{"text":"我一般会在早上喝一杯温水，然后简单的做一些拉伸运动。天天你去哪了？好可爱啊"}
```

API工作正常，识别准确。