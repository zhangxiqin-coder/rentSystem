"""
智谱OCR识别模块
支持GLM-4V模型进行水电表读数识别
"""
import os
import base64
from typing import Optional
from zhipuai import ZhipuAI


class ZhipuOCR:
    """智谱AI OCR识别器"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化智谱OCR
        
        Args:
            api_key: 智谱API密钥，默认从环境变量读取
        """
        self.api_key = api_key or os.getenv('ZHIPUAI_API_KEY')
        if not self.api_key:
            raise ValueError("智谱API密钥未设置，请设置环境变量 ZHIPUAI_API_KEY 或传入 api_key 参数")
        
        self.client = ZhipuAI(api_key=self.api_key)
        self.model = "glm-4v"  # 支持视觉的模型
    
    def encode_image(self, image_path: str) -> str:
        """
        将图片编码为base64
        
        Args:
            image_path: 图片路径
            
        Returns:
            base64编码的图片字符串
        """
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    
    def recognize_meter(
        self,
        image_path: str,
        meter_type: str = "水表",
        previous_reading: Optional[float] = None
    ) -> Optional[float]:
        """
        识别水电表读数
        
        Args:
            image_path: 图片路径
            meter_type: 表类型（水表/电表）
            previous_reading: 上次读数（用于辅助验证）
            
        Returns:
            识别的读数，失败返回None
        """
        try:
            # 编码图片
            base64_image = self.encode_image(image_path)
            
            # 构建提示词
            prompt = f"""请识别这张{meter_type}照片中的数字读数。

识别要求：
1. 这是一个{meter_type}的照片
2. 请找出数字显示区域（通常是黑色背景白色数字或机械数字轮）
3. 识别当前的完整读数（包含所有数字位）
"""
            if previous_reading is not None:
                prompt += f"4. 上次读数是 {previous_reading}，本次读数应该大于或等于上次读数\n"
            
            prompt += """
请直接输出一个数字，不要任何其他文字或标点符号。
例如：12345"""
            
            # 调用API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
                temperature=0.1,  # 低温度以获得稳定结果
                max_tokens=50
            )
            
            # 提取结果
            result_text = response.choices[0].message.content.strip()
            
            # 清理结果（提取数字）
            import re
            numbers = re.findall(r'\d+\.?\d*', result_text)
            
            if numbers:
                reading = float(numbers[0])
                
                # 验证合理性
                if previous_reading is not None and reading < previous_reading:
                    print(f"⚠️  警告: 识别读数 {reading} 小于上次读数 {previous_reading}")
                    print(f"原始识别文本: {result_text}")
                    # 不返回None，让用户决定
                    return reading
                
                return reading
            else:
                print(f"⚠️  无法从识别结果中提取数字: {result_text}")
                return None
                
        except Exception as e:
            print(f"❌ 智谱OCR识别失败: {e}")
            return None
    
    def batch_recognize(self, image_paths: list, meter_type: str = "水表") -> list:
        """
        批量识别多张图片
        
        Args:
            image_paths: 图片路径列表
            meter_type: 表类型
            
        Returns:
            识别结果列表 [(path, reading), ...]
        """
        results = []
        for path in image_paths:
            print(f"正在识别: {path}")
            reading = self.recognize_meter(path, meter_type)
            results.append((path, reading))
        return results


def test_zhipu_ocr():
    """测试智谱OCR"""
    # 需要先设置环境变量: export ZHIPUAI_API_KEY="your_key"
    
    ocr = ZhipuOCR()
    
    # 测试图片
    test_image = "test_water_meter.jpg"
    
    print("🔍 开始识别水电表...")
    reading = ocr.recognize_meter(test_image, meter_type="水表")
    
    if reading is not None:
        print(f"✅ 识别成功！读数: {reading}")
    else:
        print("❌ 识别失败")


if __name__ == "__main__":
    test_zhipu_ocr()
