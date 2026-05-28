"""
腾讯云OCR工具
"""
import os
import base64
import json
from typing import Optional
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.ocr.v20181119 import ocr_client, models


def recognize_meter_with_tencent(image_path: str) -> Optional[float]:
    """
    使用腾讯云OCR识别水电表读数

    Args:
        image_path: 图片路径

    Returns:
        识别的读数，失败返回None
    """
    try:
        # 从环境变量获取密钥
        secret_id = os.getenv("TENCENT_SECRET_ID")
        secret_key = os.getenv("TENCENT_SECRET_KEY")

        if not secret_id or not secret_key:
            print("腾讯云OCR密钥未配置")
            return None

        # 读取图片并base64编码
        with open(image_path, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')

        # 配置腾讯云OCR
        cred = credential.Credential(secret_id, secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "ocr.tencentcloudapi.com"

        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile

        # 使用ap-guangzhou区域
        client = ocr_client.OcrClient(cred, "ap-guangzhou", client_profile)

        # 调用通用印刷体识别API
        req = models.GeneralBasicOCRRequest()
        req.ImageBase64 = image_base64

        # 发送请求
        resp = client.GeneralBasicOCR(req)

        # 打印原始响应用于调试
        print(f"腾讯云OCR原始响应类型: {type(resp)}")
        print(f"腾讯云OCR响应: {resp}")

        # 提取所有文本
        all_text = ""
        if hasattr(resp, 'TextDetections') and resp.TextDetections:
            for item in resp.TextDetections:
                if hasattr(item, 'DetectedText') and item.DetectedText:
                    all_text += item.DetectedText + " "

        print(f"腾讯云OCR识别文本: {all_text}")

        # 提取数字（支持小数）
        import re
        numbers = re.findall(r'\d+\.?\d*', all_text)

        # 策略1: 找最长的数字序列（水电表读数通常是较长数字）
        long_numbers = re.findall(r'\d{4,}', all_text)  # 4位以上数字
        if long_numbers:
            readings = [float(n) for n in long_numbers]
            max_reading = max(readings)
            # 过滤明显不合理的读数
            if max_reading >= 10:
                print(f"使用最长的数字序列: {max_reading}")
                return max_reading

        # 策略2: 找最大的数字（传统方法）
        if numbers:
            readings = [float(n) for n in numbers]
            valid_readings = [r for r in readings if r >= 10]

            if valid_readings:
                max_reading = max(valid_readings)
                print(f"使用最大有效数字: {max_reading}")
                return max_reading
            elif readings:
                max_reading = max(readings)
                print(f"使用最大数字: {max_reading}")
                return max_reading

        return None

    except Exception as e:
        print(f"腾讯云OCR识别失败: {str(e)}")
        import traceback
        print(f"详细错误堆栈: {traceback.format_exc()}")
        return None
