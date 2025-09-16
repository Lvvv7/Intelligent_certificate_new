# certificate_automation.py
import time,random,os,base64,io,shutil
from PIL import Image
from pathlib import Path
import zipfile

from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from config_manager import config_manager
from state_manager import state_manager, ErrorType
import logging
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from captcha_recognizer.slider import SliderV2
import subprocess
import win32print

logger = logging.getLogger(__name__)

class CertificateAutomation:
    """证件自动化处理类 - 专注于浏览器操作"""
    
    def __init__(self):
        self.driver = None
        self.wait = None
        self.config = config_manager
    
    def __enter__(self):
        """上下文管理器入口"""
        self.setup_driver()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def setup_driver(self):
        """初始化浏览器驱动"""
        options = webdriver.EdgeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--window-size=1280,1024")
        
        # 下载配置
        prefs = {
            "download.default_directory": self.config.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)
        
        if self.config.headless:
            options.add_argument("--headless")
        
        from selenium.webdriver.edge.service import Service
        service = Service(self.config.edge_driver_path)
        self.driver = webdriver.Edge(service=service, options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 20)
        
        logger.info("浏览器驱动初始化完成")
    
# _______________________________system1_function_______________________________

    def system1_function(self, username: str, password: str):
        """系统1的处理流程"""
        try:
            with self:  # 使用上下文管理器确保资源释放
                return self._execute_system1_workflow(username, password)
        except Exception as e:
            logger.error(f"系统1处理流程异常: {str(e)}")
            return False, str(e)
            
    
    def _execute_system1_workflow(self, username: str, password: str):
        """执行系统1的具体工作流程"""
        # 获取当前状态
        state = state_manager.get_state()
        
        # 1. 打开登录页面
        login_url = "https://tyrz.zwfw.gxzf.gov.cn/am/auth/login?service=initService&goto=aHR0cHM6Ly90eXJ6Lnp3ZncuZ3h6Zi5nb3YuY24vYW0vb2F1dGgyL2F1dGhvcml6ZT9zZXJ2aWNlPWluaXRTZXJ2aWNlJmNsaWVudF9pZD16cnl0aHh0JnJlZGlyZWN0X3VyaT1odHRwcyUzQSUyRiUyRnpoamcuc2NqZGdsai5neHpmLmdvdi5jbiUzQTYwODclMkZUb3BJUCUyRnNzbyUyRm9hdXRoMiUzRmF1dGhUeXBlJTNEendmd19ndWFuZ3hpJnJlc3BvbnNlX3R5cGU9Y29kZSZzY29wZT11aWQrY24rdXNlcmlkY29kZSt1c2VydHlwZSttYWlsK3RlbGVwaG9uZW51bWJlcitpZGNhcmRudW1iZXIraWRjYXJkdHlwZSt1bml0bmFtZStvcmdhbml6YXRpb24rbG9naW5pbmZvK3Rva2VuaWQrc3ViamVjdCt1cGRhdGVUaW1lJnN0YXRlPVo4S2gycg=="
        self.driver.get(login_url)
        logger.info("登录页面已打开")
        
        # 2. 填写登录信息
        self._fill_login_info(username, password, state.user_type)
        
        # 3. 处理验证码并登录
        self._handle_login_with_retry()
        
        # 4. 导航到证件页面
        self._navigate_to_certificate_page(state.document_type)
        
        # 5. 检查证件状态
        self._check_certificate_status()
        
        # 6. 执行打印操作
        self._execute_print_operation()
        
        return True, "证件打印成功"
    
    def _fill_login_info(self, username: str, password: str, user_type: str):
        """填写登录信息"""
        try:
            # 切法人登录
            legal_login_tab = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='法人登录']"))
            )
            if user_type == 'corporate':
                logger.info("切换到法人登录")
                legal_login_tab.click()
                time.sleep(0.5)
            else:
                logger.info("当前为个人登录，无需切换")

            username_field = self.wait.until(EC.presence_of_element_located((By.ID, 'legal_login_name')))
            password_field = self.wait.until(EC.presence_of_element_located((By.ID, 'legal_pswd')))

            username_field.clear()
            username_field.send_keys(username)
            time.sleep(0.5)
            password_field.clear()
            password_field.send_keys(password)
            time.sleep(0.5)
            
            logger.info("账号和密码输入完成")
            return True
        except Exception as e:
            logger.error(f"填写登录信息失败: {str(e)}")
            raise Exception("账号密码填写异常") 
    
    def _handle_login_with_retry(self):
        """处理登录重试逻辑"""
        # 登录(带重试机制)
        max_login_attempts = 3
        for attempt in range(max_login_attempts):
            old_url = self.driver.current_url
            logger.info(f"尝试登录，第 {attempt + 1} 次")
            # 解决滑块验证码
            self._solve_slider_captcha()

            try:   # 点击登录按钮后，等待 URL 变化看看是否登录成功
                # 等待 URL 变化（1 秒内）
                WebDriverWait(self.driver, 1).until(lambda d: d.current_url != old_url)
                logger.info("登录成功，已跳转到下一页")
                break  # 登录成功，跳出重试循环
                
            except TimeoutException:
                # 1 秒后仍在登录页 ⇒ 出现了错误提示
                error_tip = self.driver.find_element(By.CSS_SELECTOR, ".err_tip .err_text")
                error_text = error_tip.text.strip()
                logger.info(f"登录失败：{error_text}")
                
                if error_text == "用户名或密码不正确":
                    raise Exception("用户名或密码不正确")
                
                elif error_text == "请进行滑块验证":
                    # 验证码相关错误，可以重试
                    if attempt < max_login_attempts - 1:  # 不是最后一次尝试
                        logger.info(f"验证码错误，准备重试 (剩余 {max_login_attempts - attempt - 1} 次)")
                        try:
                            # 重新解决滑块验证码
                            time.sleep(1)
                            if not self._solve_slider_captcha():
                                logger.error("重试时验证码识别失败")
                                time.sleep(1)
                                continue  # 继续下一次重试
                        except Exception as refresh_e:
                            logger.error(f"刷新验证码失败: {refresh_e}")
                            
                    else:
                        # 已是最后一次尝试
                        return False, "登录失败，验证码错误"
                else:
                    # 其他类型错误，不重试
                    raise Exception("登录异常")             
        
    
    def _navigate_to_certificate_page(self, document_type: str):
        """导航到证件页面"""
        time.sleep(2)
        self.driver.get(self.config.document_url[document_type])
        # 点击相关tab
        my_button = self.wait.until(
            EC.element_to_be_clickable((By.ID, "tab-second"))
        )
        ActionChains(self.driver).click(my_button).perform()
        time.sleep(2)
    
    def _check_certificate_status(self):
        """检查证件状态"""
        # 元素存在
        list = self.driver.find_elements(By.CSS_SELECTOR, "div.el-table__empty-block")
        print(list)
        print(len(list))
        if list and len(list) > 0:
            raise Exception("证件状态记录为空")
        else:
            ele = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.tni-status.tni-status__success"))
            )
            
            text = WebDriverWait(self.driver, 20).until(
                lambda d: ele.get_attribute("textContent").strip()
            )
            text = text.strip()
            logger.info(f"证件状态：{text}")

            if text == "准予":
                # 点击更多按钮进行打印
                more_btn = self.wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, '/html/body/div[1]/div[2]/div/div[1]/div[2]/div/div[2]/div[2]/div/div/div[2]/div/div[3]/table/tbody/tr/td[7]/div/div/div/button')
                    )
                )
                more_btn.click()
                time.sleep(2)
                print_btn = self.wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, '/html/body/ul/li[2]/button')
                    )
                )
                print_btn.click()
                time.sleep(2)

                # 如果文件夹非空，解压文件夹中下载的文件
                if os.listdir(self.config.download_dir):
                    # 先清空目标文件夹
                    if os.path.exists(self.config.extract_path):
                        shutil.rmtree(self.config.extract_path)
                    os.makedirs(self.config.extract_path, exist_ok=True)
                    self._extract_zip_file(self.config.download_dir, self.config.extract_path)
            else:
                raise Exception(f"证件状态异常: {text}")

    def _execute_print_operation(self):
        """执行打印操作"""
        self._print_document(self.config.printer_name, self.config.extract_path)

    # 实际滑动函数
    def _solve_slider_captcha(self):
        """解决滑块验证码"""
        try:
            # 先找到滑块并按住 → 背景图才会加载
            slider_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//div[@id='mpanel2']//div[contains(@class,'verify-move-block')]"))
            )
            action = ActionChains(self.driver)
            action.move_to_element(slider_button).click_and_hold(slider_button).perform()
            time.sleep(3)  # 等背景图渲染

            # 背景图出现
            captcha_element = self.wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "#mpanel2 .backImg"))
            )
            web_image_width = captcha_element.size['width']
            logger.info(f"网页验证码图片宽度: {web_image_width}")

            # 识别并算拖动距离
            drag_distance = self._get_drag_distance_with_retry(web_image_width, max_retry=5)

            # 继续拖动
            track = self._generate_human_like_track(drag_distance)
            logger.info(f"开始拖动滑块，轨迹步数: {len(track)}，总距离：{drag_distance}")

            for move in track:
                action.move_by_offset(xoffset=move, yoffset=random.uniform(-1, 1)).perform()
                time.sleep(random.uniform(0.01, 0.03))

            action.release().perform()
            logger.info("滑块拖动完成")

            # 点击登录按钮
            login_btn = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="form_lists"]/div[1]/div[2]/button'))
            )
            time.sleep(0.5)
            login_btn.click()

            return True
            
        except Exception as e:
            logger.error(f"解决滑块验证码失败: {str(e)}")
            raise Exception("验证码识别失败")
        
    # 计算滑块拖动距离
    def _get_drag_distance_with_retry(self, web_image_width, max_retry=None):
        """获取滑块拖动距离，识别失败会自动刷新图片重试"""
        if max_retry is None:
            max_retry = 3
            
        for attempt in range(1, max_retry + 1):
            try:
                captcha_img = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#mpanel2 .backImg"))
                )
                src_data = captcha_img.get_attribute("src")
                if not src_data.startswith("data:image"):
                    raise RuntimeError("验证码图片src异常")

                bg_b64 = src_data.split("base64,")[1]
                bg_bytes = base64.b64decode(bg_b64)

                # 保存图片到本地临时文件
                IMG_DIR = self.config.img_dir
                tt = time.time()
                img_name = f'{tt}_image.png'
                img_abs_path = os.path.join(IMG_DIR, img_name)

                # 确保目录存在
                os.makedirs(IMG_DIR, exist_ok=True)
                
                with open(img_abs_path, "wb") as f:
                    f.write(bg_bytes)

                logger.info(f"第{attempt}次尝试：调用本地模型识别缺口位置...")
                box, _ = SliderV2().identify(source=img_abs_path, show=False)

                if not box:
                    raise RuntimeError("未能识别出缺口位置")

                raw_x = float(box[0])
                logger.info(f"识别出的原始缺口X坐标: {raw_x}")

                # 计算缩放
                with Image.open(io.BytesIO(bg_bytes)) as img:
                    orig_w = float(img.width)

                scale = web_image_width / orig_w if orig_w else 1.0
                initial_slider_x = 12
                distance = (raw_x - initial_slider_x) * scale

                logger.info(f"网页图片宽度: {web_image_width}, 原始图片宽度: {orig_w}")
                logger.info(f"缩放比例: {scale:.4f}, 拖动距离: {distance:.2f}")

                return max(1, int(distance))

            except RuntimeError as e:
                logger.error(f"识别失败: {e}")
                if attempt < max_retry:
                    logger.info("点击刷新图片按钮重试...")
                    try:
                        refresh_btn = self.wait.until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="mpanel2"]/div[1]/div/div/i'))
                        )
                        refresh_btn.click()
                        time.sleep(2)
                    except Exception as refresh_e:
                        logger.error(f"刷新验证码失败: {refresh_e}")
                else:
                    raise RuntimeError("达到最大重试次数，仍未识别出缺口位置")
    
    # 生成类人的拖动轨迹
    def _generate_human_like_track(self, distance):
        """生成类人的拖动轨迹"""
        track, current = [], 0.0  # track: 轨迹列表(一次拖动多少像素), current: 当前滑块位置
        mid = distance * random.uniform(0.6, 0.8)   # 中点，随机创建（并非每次中点都是二分之一而是在这附近）
        t, v = 0.2, 0.0
        while current < distance:
            a = random.uniform(2, 4) if current < mid else -random.uniform(3, 5)  # 当在中点前时加速，过了中点后减速（加速度为负）
            v0 = v  # v0:初速度
            v = max(v0 + a * t, 0)
            move = v0 * t + 0.5 * a * (t ** 2)  # move: 每次移动的距离
            move = max(1, move)    # 保证每次至少移动1像素，避免陷入死循环
            if current + move > distance: 
                move = distance - current # 最后一次直接移动到终点
            current += move
            track.append(int(round(move)))
        return track
    
    # 文件解压函数
    def _extract_zip_file(self, src_dir: str, dst_dir: str, enc='gbk'):
        src_path = Path(src_dir)
        dst_path = Path(dst_dir)
        dst_path.mkdir(parents=True, exist_ok=True)

        for zf in src_path.rglob("*.zip"):
            target_dir = dst_path / zf.stem
            counter = 1
            while target_dir.exists():
                target_dir = dst_path / f"{zf.stem}_{counter}"
                counter += 1

            try:
                with zipfile.ZipFile(zf, 'r') as zip_ref:
                    for info in zip_ref.infolist():
                        # 1. 用 GBK 解码文件名
                        name = info.filename.encode('cp437').decode(enc)
                        target_file = target_dir / name
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        # 2. 写文件
                        if info.is_dir():
                            target_file.mkdir(exist_ok=True)
                        else:
                            with zip_ref.open(info) as src, open(target_file, 'wb') as dst:
                                dst.write(src.read())
                logger.info(f"解压完成：{zf} → {target_dir}")
                for item in src_path.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                logger.info("已清空 src_dir 中的所有文件/子目录")
            except Exception as e:
                logger.error(f"解压失败：{zf}，原因：{e}")

    # 获取指定打印机的状态
    def _get_printer_status(self,printer_name: str) -> str:
        try:
            h_printer = win32print.OpenPrinter(printer_name)
            status = win32print.GetPrinter(h_printer, 2)["Status"]
            win32print.ClosePrinter(h_printer)
        except Exception as e:
            return f"打开打印机失败：{e}"

        if status == 0:
            return "就绪"

        # desc_list = [desc for flag, desc in STATUS_MAP.items() if status & flag]
        raise Exception("打印机状态异常")

    # 检查 PDFtoPrinter 程序是否存在
    def  _ensure_pdftoprinter(self):
        print(self.config.pdfto_printer_exe)
        if os.path.isfile(self.config.pdfto_printer_exe):
            logger.info("打印程序存在")
            return self.config.pdfto_printer_exe
        logger.info("打印程序不存在")
        raise Exception("打印程序不存在")

    # 打印机打印函数
    def _print_document(self, printer_name: str, pdf_folder: str) -> None:
        # 1. 检查 PDF 文件夹是否存在
        if not os.path.isdir(pdf_folder):
            logger.error("PDF 文件夹不存在")
            return {"success": False, "message": "PDF 文件夹不存在"}
        logger.info("PDF 文件夹存在")

        # 2. 检查打印机状态
        status = self._get_printer_status(printer_name)
        if status != "就绪":
            raise Exception("打印机状态异常")
        logger.info("打印机状态正常")

        # 3. 检查 PDFtoPrinter
        exe = self._ensure_pdftoprinter()
        # 4. 下发打印任务
        for pdf_file in Path(pdf_folder).rglob("*.pdf"):
            logger.info(f"开始执行打印")
            cmd = [exe, str(pdf_file), printer_name]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                logger.info(f"已发送打印任务：{pdf_file}")
            except subprocess.CalledProcessError as e:
                logger.error(f"打印任务失败：{e.stderr.decode(errors='ignore')}")
                return {"success": False, "message": f"打印任务失败：{e.stderr.decode(errors='ignore')}"}

        # 5. 轮询直到完成或出错
        while True:
            status = self._get_printer_status(printer_name)
            if status == "就绪":
                return {"success": True, "message": "打印完成"}
            elif status == "正在打印":
                time.sleep(0.5)
                continue
            else:
                return {"success": False, "message": f"打印异常：{status}"}
            

# _______________________________system2_function_______________________________
    def system2_function(self, username: str, password: str):
        """系统2的处理流程"""
        try:
            with self:  # 使用上下文管理器确保资源释放
                return self._execute_system2_workflow(username, password)
        except Exception as e:
            logger.error(f"系统2处理流程异常: {str(e)}")
            return False, str(e)

    def _execute_system2_workflow(self, username: str, password: str):
        """执行系统2的具体工作流程"""
        pass