"""
水电表读数OCR识别API
支持Tesseract OCR、智谱AI OCR和腾讯云OCR
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
import tempfile
import os
import re
from PIL import Image
import pytesseract
from typing import Optional

router = APIRouter()

# OCR引擎选择
OCR_ENGINE = os.getenv("OCR_ENGINE", "tencent")  # 默认使用腾讯云OCR


async def recognize_with_tesseract(image: UploadFile = File(...)):
    """使用Tesseract OCR识别"""
    temp_file = None
    try:
        # 保存到临时文件
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, f"meter_reading_{os.urandom(8).hex()}.jpg")

        # 保存上传的图片
        with open(temp_file, "wb") as f:
            content = await image.read()
            f.write(content)

        # 使用PIL打开图片
        img = Image.open(temp_file)

        # 图片增强处理
        # 1. 转换为RGB（如果是RGBA）
        if img.mode == 'RGBA':
            img = img.convert('RGB')

        # 2. 放大图片以提高识别率（如果图片太小）
        width, height = img.size
        if max(width, height) < 800:
            scale = 800 / max(width, height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # 3. 转换为灰度图提高识别率
        img = img.convert('L')

        # 4. 增强对比度
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # 5. 二值化处理（黑白分明）
        threshold = 128
        img = img.point(lambda x: 0 if x < threshold else 255, '1')

        # 使用Tesseract识别，配置为识别数字
        # --psm 7: 单行文本
        # --psm 6: 单个文本块（如果psm 7不work）
        # -c tessedit_char_whitelist=0123456789.: 只识别数字和小数点
        text = pytesseract.image_to_string(
            img,
            config='--psm 6 -c tessedit_char_whitelist=0123456789.'
        ).strip()

        # 尝试提取数字
        numbers = re.findall(r'\d+\.?\d*', text)

        if numbers:
            # 取第一个数字作为读数
            try:
                reading = float(numbers[0])
                confidence = "AI识别成功（Tesseract），请核对"
            except ValueError:
                reading = 0.0
                confidence = "识别失败，请手动输入"
        else:
            reading = 0.0
            confidence = "未识别到数字，请手动输入"

        return {
            "reading": reading,
            "confidence": confidence,
            "engine": "tesseract"
        }

    except Exception as e:
        return {
            "reading": 0.0,
            "confidence": f"识别失败: {str(e)}",
            "engine": "tesseract"
        }
    finally:
        # 清理临时文件
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass


async def recognize_with_zhipu(image: UploadFile = File(...), meter_type: str = "水表"):
    """使用智谱AI OCR识别"""
    try:
        from app.utils.zhipu_ocr_service import ZhipuOCRService
        
        # 保存到临时文件
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, f"meter_reading_{os.urandom(8).hex()}.jpg")
        
        with open(temp_file, "wb") as f:
            content = await image.read()
            f.write(content)
        
        # 初始化智谱OCR
        ocr = ZhipuOCRService()
        
        # 识别读数
        reading = ocr.recognize_meter(temp_file, meter_type=meter_type)
        
        # 清理临时文件
        try:
            os.remove(temp_file)
        except:
            pass
        
        if reading is not None:
            return {
                "reading": reading,
                "confidence": "AI识别成功（智谱GLM-4V），请核对",
                "engine": "zhipu"
            }
        else:
            return {
                "reading": 0.0,
                "confidence": "智谱OCR识别失败，请手动输入",
                "engine": "zhipu"
            }
            
    except ImportError:
        return {
            "reading": 0.0,
            "confidence": "智谱OCR模块未安装，请检查配置",
            "engine": "zhipu"
        }
    except Exception as e:
        return {
            "reading": 0.0,
            "confidence": f"智谱OCR识别失败: {str(e)}",
            "engine": "zhipu"
        }


async def recognize_with_tencent(image: UploadFile = File(...)):
    """使用腾讯云OCR识别"""
    try:
        from app.utils.tencent_ocr import recognize_meter_with_tencent
        
        # 保存到临时文件
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, f"meter_reading_{os.urandom(8).hex()}.jpg")
        
        with open(temp_file, "wb") as f:
            content = await image.read()
            f.write(content)
        
        # 使用腾讯云OCR识别
        reading = recognize_meter_with_tencent(temp_file)
        
        # 清理临时文件
        try:
            os.remove(temp_file)
        except:
            pass
        
        if reading is not None:
            return {
                "reading": reading,
                "confidence": "AI识别成功（腾讯云OCR），请核对",
                "engine": "tencent"
            }
        else:
            return {
                "reading": 0.0,
                "confidence": "腾讯云OCR识别失败，请手动输入",
                "engine": "tencent"
            }
            
    except ImportError:
        return {
            "reading": 0.0,
            "confidence": "腾讯云OCR模块未安装，请检查配置",
            "engine": "tencent"
        }
    except Exception as e:
        return {
            "reading": 0.0,
            "confidence": f"腾讯云OCR识别失败: {str(e)}",
            "engine": "tencent"
        }


@router.post("/ocr/reading")
async def recognize_meter_reading(
    image: UploadFile = File(...),
    engine: Optional[str] = Form(None),
    meter_type: Optional[str] = Form("水表")
):
    """
    识别水电表读数

    Args:
        image: 上传的水表或电表照片
        engine: OCR引擎 (tesseract/zhipu/tencent)，默认使用环境变量或腾讯云OCR
        meter_type: 表类型 (水表/电表)

    Returns:
        {
            "reading": float,  # 识别的读数
            "confidence": str  # 置信度描述
            "engine": str  # 使用的OCR引擎
        }
    """
    # 验证文件类型
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")
    
    # 选择OCR引擎
    selected_engine = engine or OCR_ENGINE
    
    if selected_engine == "zhipu":
        return await recognize_with_zhipu(image, meter_type)
    elif selected_engine == "tencent":
        return await recognize_with_tencent(image)
    else:
        return await recognize_with_tesseract(image)


@router.get("/ocr/engines")
async def get_ocr_engines():
    """获取可用的OCR引擎列表"""
    return {
        "engines": ["tesseract", "zhipu", "tencent"],
        "default": OCR_ENGINE,
        "current_config": {
            "OCR_ENGINE": OCR_ENGINE,
            "ZHIPUAI_API_KEY": bool(os.getenv("ZHIPUAI_API_KEY")),
            "TENCENT_SECRET_ID": bool(os.getenv("TENCENT_SECRET_ID")),
            "TENCENT_SECRET_KEY": bool(os.getenv("TENCENT_SECRET_KEY"))
        }
    }
