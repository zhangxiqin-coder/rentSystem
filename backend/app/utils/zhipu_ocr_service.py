"""
智谱OCR识别模块（使用GLM-4V视觉模型）
使用智谱AI的GLM-4V模型进行OCR识别
"""
import os
import base64
import re
from typing import Optional
from zhipuai import ZhipuAI


class ZhipuOCRService:
    """智谱AI OCR识别服务（使用GLM-4V）"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化智谱OCR服务
        
        Args:
            api_key: 智谱API密钥，默认从环境变量读取
        """
        self.api_key = api_key or os.getenv('ZHIPUAI_API_KEY')
        if not self.api_key:
            raise ValueError("智谱API密钥未设置，请设置环境变量ZHIPUAI_API_KEY或传入api_key参数")
        
        self.client = ZhipuAI(api_key=self.api_key)
    
    def _encode_image(self, image_path: str) -> str:
        """
        将图片编码为base64
        
        Args:
            image_path: 图片路径
            
        Returns:
            base64编码的图片
        """
        with open(image_path, 'rb') as f:
            image_data = f.read()
        return base64.b64encode(image_data).decode('utf-8')
    
    def _filter_red_pixels(self, image_path: str) -> Optional[str]:
        """
        过滤电表图片中的红色像素（红色小数点）
        只保留黑色/灰色数字，去除红色区域
        
        Args:
            image_path: 原始图片路径
            
        Returns:
            处理后的图片路径（临时文件），失败返回None
        """
        try:
            from PIL import Image
            import tempfile
            
            # 打开图片
            img = Image.open(image_path)
            
            # 转换为RGB模式
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 获取像素数据
            pixels = img.load()
            width, height = img.size
            
            # 创建新图片
            new_img = Image.new('RGB', (width, height), color='white')
            new_pixels = new_img.load()
            
            # 遍历每个像素
            for y in range(height):
                for x in range(width):
                    r, g, b = pixels[x, y]
                    
                    # 判断是否为红色像素（R值显著高于G和B）
                    # 红色特征：R > 150 且 R > G*1.5 且 R > B*1.5
                    is_red = r > 150 and r > g * 1.5 and r > b * 1.5
                    
                    if is_red:
                        # 红色像素替换为白色（去掉红色小数点）
                        new_pixels[x, y] = (255, 255, 255)
                    else:
                        # 其他像素保持原样
                        new_pixels[x, y] = (r, g, b)
            
            # 保存到临时文件
            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            # 保存处理后的图片
            new_img.save(temp_path, 'JPEG', quality=95)
            
            print(f"✅ 红色过滤完成，保存到: {temp_path}")
            return temp_path
            
        except Exception as e:
            print(f"❌ 红色过滤失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def recognize_meter(
        self,
        image_path: str,
        meter_type: str = "水表",
        previous_reading: Optional[float] = None,
        model: str = "glm-4v-flash"  # 使用flash版本，更便宜更快
    ) -> Optional[float]:
        """
        识别水电表读数（使用GLM-4V视觉模型）
        
        Args:
            image_path: 图片路径
            meter_type: 表类型（水表/电表）
            previous_reading: 上次读数（用于辅助验证）
            model: 使用的模型 (glm-4v-flash/glm-4v/glm-4v-plus)
            
        Returns:
            识别的读数，失败返回None
        """
        try:
            print(f"🔍 调用智谱OCR服务: {image_path}")
            
            # 检查文件是否存在
            if not os.path.exists(image_path):
                print(f"❌ 文件不存在: {image_path}")
                return None
            
            # 电表特殊处理：过滤红色像素
            if meter_type == "电表":
                processed_image = self._filter_red_pixels(image_path)
                if processed_image:
                    image_path = processed_image
                    print(f"✅ 电表红色过滤完成")
            
            # 编码图片
            image_base64 = self._encode_image(image_path)
            
            # 构建提示词
            prompt = f"""请仔细识别这张{meter_type}的照片。
            
任务：
1. 找到表盘上显示的数字读数
2. 只返回识别到的数字，不要返回任何其他文字
3. 如果有多个数字，选择最可能是当前读数的那个（通常是最大的数字）

注意：
|- 这可能是{meter_type}的数字显示
|- 只返回纯数字，不要"读数是"、"数字为"等前缀
|- 电表：只读取整数部分的4位数字（如7617），忽略红色的小数点位数（如36）
|- 水表：读取完整的数字读数"""
            
            # 调用GLM-4V API
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
                temperature=0.1  # 降低随机性，提高准确性
            )
            
            # 提取识别结果
            if not response or not response.choices:
                print(f"❌ API响应无效")
                return None
            
            result_text = response.choices[0].message.content.strip()
            print(f"📝 模型返回: {result_text}")
            
            # 提取数字
            numbers = re.findall(r'\d+\.?\d*', result_text)
            
            if not numbers:
                print("⚠️  未找到数字")
                return None
            
            # 取最长的数字串（通常是完整读数）
            reading = float(max(numbers, key=lambda x: len(str(x).replace('.', ''))))
            
            # 电表特殊后处理：如果识别出5-6位数字，取前4位作为整数部分
            if meter_type == "电表":
                reading_str = str(reading).replace('.', '')
                if len(reading_str) >= 5:
                    # 取前4位作为整数读数
                    reading = float(reading_str[:4])
                    print(f"✂️  电表后处理：取前4位 {reading}")
            
            # 验证合理性
            if previous_reading is not None and reading < previous_reading * 0.5:
                print(f"⚠️  警告: 识别读数 {reading} 远小于上次读数 {previous_reading}，可能识别错误")
                # 仍然返回，但给出警告
            
            print(f"✅ 最终读数: {reading}")
            return reading
            
        except Exception as e:
            error_msg = str(e)
            if "余额不足" in error_msg or "1113" in error_msg:
                print(f"❌ 智谱AI账户余额不足，请充值后重试")
            elif "429" in error_msg:
                print(f"❌ API调用次数超限或余额不足")
                print(f"💡 提示: 尝试使用 glm-4v-flash 模型（更便宜）")
            else:
                print(f"❌ 智谱OCR识别失败: {e}")
            import traceback
            traceback.print_exc()
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
            print(f"\n{'='*60}")
            print(f"正在识别: {path}")
            reading = self.recognize_meter(path, meter_type)
            results.append((path, reading))
        return results


def test_zhipu_ocr():
    """测试智谱OCR服务"""
    import os
    api_key = os.getenv('ZHIPUAI_API_KEY')
    if not api_key:
        print("❌ 请设置环境变量 ZHIPUAI_API_KEY")
        return
    
    ocr = ZhipuOCRService()
    
    # 测试图片
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (300, 150), color='white')
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), '12345', fill='black')
    test_image = '/tmp/test_water_meter.jpg'
    img.save(test_image)
    
    print("🔍 开始识别水电表...")
    reading = ocr.recognize_meter(test_image, meter_type="水表")
    
    if reading is not None:
        print(f"✅ 识别成功！读数: {reading}")
    else:
        print("❌ 识别失败")


if __name__ == "__main__":
    test_zhipu_ocr()
