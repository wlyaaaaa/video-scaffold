import os
import sys
import subprocess
import time
import moderngl
import numpy as np

# Console may be GBK on Windows; keep emoji prints from crashing.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    WIDTH, HEIGHT = 3840, 2160
    FPS = 60

    # 60s @ 60fps. The orbit/flow periods all divide 60s, so the clip loops
    # seamlessly; the render pipeline also stream-loops it for any duration.
    DURATION = 60

    TOTAL_FRAMES = FPS * DURATION
    OUTPUT_FILENAME = os.path.join(HERE, "background_4k.mp4")
    SHADER_FILE = os.path.join(HERE, "fluid_glass.comp")

    print(f"================ 通用流体玻璃背景渲染（4K60 / 60s 无缝循环 SDR） ================")
    
    try:
        ctx = moderngl.create_standalone_context(require=430)
    except Exception as e:
        print(f"❌ 错误: 无法创建 OpenGL 4.3 上下文: {e}")
        sys.exit(1)

    print(f"📊 独显金牌算力就位: {ctx.info.get('GL_RENDERER', 'Unknown')}")

    if not os.path.exists(SHADER_FILE):
        print(f"❌ 错误: 未找到着色器文件 {SHADER_FILE}")
        sys.exit(1)
        
    with open(SHADER_FILE, 'r', encoding='utf-8') as f:
        comp_code = f.read()

    try:
        program = ctx.compute_shader(comp_code)
    except Exception as e:
        print(f"❌ 计算着色器编译失败:\n{e}")
        sys.exit(1)

    # 坚持经典 f1 避坑独立显存容器
    tex = ctx.texture((WIDTH, HEIGHT), 4, dtype='f1')

    if 'u_resolution' in program:
        program['u_resolution'].value = (float(WIDTH), float(HEIGHT))

    # -------------------------------------------------------------
    # 🎛️ 终极对齐：用 -cq 22 锁死英伟达常量质量，压碎无损 1GB 毒瘤
    # -------------------------------------------------------------
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-pix_fmt', 'rgba', '-s', f"{WIDTH}x{HEIGHT}", '-r', str(FPS),
        '-i', '-', 
        '-c:v', 'av1_nvenc',             # NVIDIA NVENC AV1 核心
        '-preset', 'p5',                 # 预设 P5 慢速（高质量）
        '-tune', 'hq',                   # 调节 高质量
        '-rc', 'constqp',                # 比特率控制 恒定 QP
        '-cq', '22',                     # 🎯 核心修正：用 -cq 替代 -qp，真正激活 22 号恒定质量压缩
        '-spatial-aq', '1',              # 自适应量化
        '-pix_fmt', 'yuv420p10le',       # 10-Bit 无损色深过渡
        OUTPUT_FILENAME
    ]

    try:
        ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10**8)
    except FileNotFoundError:
        print("❌ 错误: 未找到 FFmpeg，请检查环境变量。")
        sys.exit(1)

    grid_x = WIDTH // 16
    grid_y = HEIGHT // 16

    print(f"\n[GPU 计算] 右上角巡航起跑，正在拦截前 {TOTAL_FRAMES} 帧高速落盘...")
    start_time = time.time()

    try:
        for frame_idx in range(TOTAL_FRAMES):
            if ffmpeg_process.poll() is not None:
                _, stderr_data = ffmpeg_process.communicate()
                print(f"❌ 错误: FFmpeg 进程意外终止，底层报错信息如下:\n{stderr_data.decode('utf-8')}")
                sys.exit(1)

            current_time = frame_idx / float(FPS)
            if 'u_time' in program:
                program['u_time'].value = current_time

            tex.bind_to_image(0, read=False, write=True)
            program.run(grid_x, grid_y, 1)
            ctx.finish()
            
            pixel_data = tex.read()
            ffmpeg_process.stdin.write(pixel_data)

            if (frame_idx + 1) % 60 == 0:
                print(f" 🟩 进度: {frame_idx + 1}/{TOTAL_FRAMES} 帧高透数据落盘...")

        ffmpeg_process.stdin.close()
        ffmpeg_process.communicate()
        
    except Exception as e:
        print(f"❌ 运行期异常: {e}")
        try:
            ffmpeg_process.stdin.close()
        except:
            pass
        stderr_data = ffmpeg_process.stderr.read()
        if stderr_data:
            print(f"📋 FFmpeg 底层错误日志详情:\n{stderr_data.decode('utf-8', errors='ignore')}")
        ffmpeg_process.kill()
        sys.exit(1)

    render_duration = time.time() - start_time
    print(f"✨ 背景渲染完成！总耗时: {render_duration:.2f} 秒")
    print(f" 🎉 4K60 无缝循环背景已就绪: {OUTPUT_FILENAME}")

    tex.release(); program.release(); ctx.release()

if __name__ == '__main__':
    main()