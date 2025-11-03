import mss
import numpy as np
import time
import ctypes
import sys
from ctypes import wintypes
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SendInput = ctypes.windll.user32.SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)
wait_time = 3.15
if len(sys.argv) > 1:
        try:
            wait_time = float(sys.argv[1])
        except ValueError:
            print("错误：参数必须是一个数字")
            sys.exit(1)
# 结构体定义
class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]

class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long),  # 修正：应该是 c_long
                ("y", ctypes.c_long)]

# 键盘函数
def PressKey(hexKeyCode):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(0, hexKeyCode, 0x0008, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def ReleaseKey(hexKeyCode):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(0, hexKeyCode, 0x0008 | 0x0002, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

# 鼠标函数
def get_mpos():
    orig = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(orig))
    return int(orig.x), int(orig.y)

def set_mpos(pos):
    x, y = pos
    ctypes.windll.user32.SetCursorPos(x, y)

def mouse_click(pos, button='left'):
    """完整的鼠标点击函数"""
    set_mpos(pos)
    time.sleep(0.01)
    
    # 鼠标按下
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    flags = 0x0002 if button == 'left' else 0x0008  # 左键或右键按下
    ii_.mi = MouseInput(0, 0, 0, flags, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(0), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))
    
    time.sleep(0.05)
    
    # 鼠标释放
    flags = 0x0004 if button == 'left' else 0x0010  # 左键或右键释放
    ii_.mi = MouseInput(0, 0, 0, flags, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(0), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

class RealtimeMonitor:
    def __init__(self, region):
        self.region = {
            'left': region[0],
            'top': region[1],
            'width': region[2],
            'height': region[3]
        }
        self.sct = mss.mss()
        self.last_white_time = 0
        self.total_calls = 0
        self.last_shot_time = 0
        self.last_100_shot_time = 0
        self.debounce_delay = 0.1  # 防抖延迟(秒)
        self.hdc = user32.GetDC(0)
    
    def __del__(self):
        """析构时释放资源"""
        if hasattr(self, 'hdc'):
            user32.ReleaseDC(0, self.hdc)

    def is_region_white_fast(self, threshold=0.3):
        """性能最高的白色检测 - 针对固定100x1区域"""
        try:
            # 使用mss高速截图
            screenshot = self.sct.grab(self.region)
            self.last_shot_time = time.perf_counter()
            self.total_calls += 1
            if self.total_calls % 100 == 0:
                tillLastShot = time.perf_counter() - self.last_100_shot_time
                self.last_100_shot_time = time.perf_counter()
                print(f"距离上100次截图: {tillLastShot:.3f}s")

            img = np.array(screenshot)
            
            # 预计算所需白色像素数量
            #required_white = 98  # 100 * 0.98 = 98
            white_count = np.count_nonzero(
                    (img[:, :, 0] >= 230) & 
                    (img[:, :, 1] >= 200) & 
                    (img[:, :, 2] >= 200)
                )
            #return white_count >= required_white
            return white_count >= threshold*self.region['width']*self.region['height']
        
        except Exception as e:
            print(f"截图错误: {e}")
            return False
        
# 创建相机实例

    def get_pixel_color(self, x, y):
        """获取单个像素颜色 (BGR格式)"""
        color = gdi32.GetPixel(self.hdc, x, y)
        if color == -1:
            print("获取像素颜色失败")
            return None
        r = color & 0xff
        g = (color >> 8) & 0xff
        b = (color >> 16) & 0xff
        return (b, g, r)
    
    def is_pixel_white(self, x, y, threshold=250):
        """检查单个像素是否为白色"""
        color = self.get_pixel_color(x, y)
        if color is None:
            return False
        return all(c >= threshold for c in color)
    
    def is_region_white(self):
        self.total_calls += 1
        self.last_shot_time = time.perf_counter()
        if self.total_calls % 100 == 0:
            tillLastShot = time.perf_counter() - self.last_100_shot_time
            self.last_100_shot_time = time.perf_counter()
            print(f"距离上100次截图: {tillLastShot:.3f}s")
        return self.is_pixel_white(900, 100)and self.is_pixel_white(950, 100) and self.is_pixel_white(1000, 100)


    def send_key_to_game(self):
        """向游戏发送按键（使用Windows API）"""
        # PressKey(0x12)  # 长e
        # time.sleep(1)
        # ReleaseKey(0x12)
        # time.sleep(0.5)#等后摇
        # PressKey(0x11)  # 小步前进
        # time.sleep(0.45)
        # ReleaseKey(0x11) 
        # PressKey(0x03)  # 切2号位
        # time.sleep(0.1)
        # ReleaseKey(0x03)
        time.sleep(wait_time-3.14)#找时机
        PressKey(0x12)  # 按下E键
        time.sleep(0.05)
        ReleaseKey(0x12)
        time.sleep(1)
    
    def start_realtime_monitor(self, check_interval=0.02):  # 20ms检查间隔
        """启动实时监控"""
        print(f"开始实时监控 - 区域: {self.region}")
        #print("监控频率: {:.0f}Hz".format(1/check_interval))
        
        try:
            while True:
                current_time = time.time()
                
                if self.is_region_white_fast():
                    # 防抖处理，避免重复触发
                    if current_time - self.last_white_time > self.debounce_delay:
                        print("检测到白色区域，执行动作...")
                        self.last_white_time = current_time
                        self.send_key_to_game()
                        tillLastShot = time.perf_counter() - self.last_shot_time                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           
                        print(f"执行耗时: {tillLastShot:.3f}s")
                        print("动作执行完成")
                
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print("监控已停止")

# 使用示例
if __name__ == "__main__":
    # 设置监控区域 (x, y, width, height)
    #monitor_region = (-1100, 99, 100, 1)  # 调整为你需要的区域
    monitor_region = (956, 386, 18, 20)  # 调整为你需要的区域
    monitor = RealtimeMonitor(monitor_region)
    monitor.start_realtime_monitor(check_interval=0.0)  