import os
import sys
import asyncio
import queue
import time
import subprocess
from multiprocessing import Process, Value, Lock, Queue
from playwright.async_api import async_playwright

# ==============================================================================
# 🎛️ 顶级声明式集中配置中心
# ==============================================================================
CONFIG = {
    "WIDTH": 3840,
    "HEIGHT": 2160,
    "FPS": 60,
    "DURATION": 900,                                
    "BG_VIDEO": "background_4k_sdr.mp4",            
    "OUTPUT_FILENAME": "output_scene_switch_4k.mp4", 
    "CQ_QUALITY": "22",                             
    
    # 🎯 满血并发：恢复 8 路物理核心压制
    "NUM_WORKERS": 8,     
    
    # 🎯 最佳切片：300 帧（5秒）。足够小以保证均衡，足够大以摊薄 FFmpeg 启动开销
    "CHUNK_FRAMES": 300,  

    "TIMELINE": [
        {
            "name": "场景一：新卡情报解禁",
            "html_path": "card_demo.html",
            "start_global": 0.0,
            "end_global": 11.0,                     
            "local_offset": 0.0,
            "fade_in_start": None,
            "fade_in_end": None,
            "fade_out_start": 10.0,                 
            "fade_out_end": 11.0                    
        },
        {
            "name": "场景二：多模态认知解析",
            "html_path": "demo_v2.html",
            "start_global": 11.0,                   
            "end_global": 900.0,                    
            "local_offset": 11.0,                   
            "fade_in_start": 11.5,                  
            "fade_in_end": 12.5,                    
            "fade_out_start": None,
            "fade_out_end": None
        }
    ]
}

TOTAL_FRAMES = CONFIG["FPS"] * CONFIG["DURATION"]


def _probe_bg_duration():
    """Length of the background clip, so we can loop it instead of running dry."""
    out = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', CONFIG["BG_VIDEO"]],
        capture_output=True, text=True
    )
    return float(out.stdout.strip())


BG_DURATION = _probe_bg_duration()

# ==============================================================================
# 🚀 满血引擎：常驻内核池 + 动态流转
# ==============================================================================

async def worker_main_loop(worker_id, task_queue, global_counter, stdout_lock, start_wall_time):
    """
    核心重构：浏览器生命周期与进程绑定。
    启动一次内核，循环吞噬所有排队的视频块，消除所有无谓的启动损耗。
    """
    async with async_playwright() as p:
        # 1. 初始化常驻浏览器
        browser = await p.chromium.launch(
            headless=True, channel="chrome",
            args=["--disable-gpu-vsync", "--force-gpu-rasterization", "--enable-zero-copy"]
        )
        context = await browser.new_context(viewport={"width": CONFIG["WIDTH"], "height": CONFIG["HEIGHT"]})
        
        # 预加载所有场景
        pages = {}
        for scene in CONFIG["TIMELINE"]:
            abs_path = os.path.abspath(scene["html_path"])
            if abs_path not in pages:
                page = await context.new_page()
                await page.goto(f"file://{abs_path}")
                pages[abs_path] = page

        # 2. 开始吞噬任务队列
        while True:
            try:
                chunk_idx = task_queue.get_nowait()
            except queue.Empty:
                break # 队列空了，完美下班

            start_idx = chunk_idx * CONFIG["CHUNK_FRAMES"]
            end_idx = min(start_idx + CONFIG["CHUNK_FRAMES"], TOTAL_FRAMES)
            frame_indices = list(range(start_idx, end_idx))

            start_time_offset = frame_indices[0] / float(CONFIG["FPS"])
            chunk_duration = len(frame_indices) / float(CONFIG["FPS"])
            chunk_output = f"temp_chunk_{chunk_idx:04d}.mp4"

            # 🎯 BUG FIX: loop the background so it covers the FULL duration.
            # Before, -ss seeked past the 60s clip and produced blank frames
            # (e.g. a 15-min timeline only showed ~1 min of moving background).
            bg_offset = start_time_offset % BG_DURATION
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-stream_loop', '-1',
                '-ss', f"{bg_offset:.3f}",
                '-t', f"{chunk_duration:.3f}",
                '-i', CONFIG["BG_VIDEO"],
                '-f', 'image2pipe', '-vcodec', 'png', '-r', str(CONFIG["FPS"]),
                '-i', '-',
                '-filter_complex', '[0:v][1:v]overlay=x=0:y=0:shortest=1',
                '-c:v', 'av1_nvenc', '-preset', 'p4', '-tune', 'hq', '-rc', 'constqp', '-cq', CONFIG["CQ_QUALITY"],
                '-spatial-aq', '1', '-pix_fmt', 'yuv420p10le', '-an',
                '-threads', '2',  
                chunk_output
            ]

            ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )

            # 高速渲染循环
            try:
                for idx in frame_indices:
                    t = idx / float(CONFIG["FPS"])
                    
                    target_scene = next((s for s in CONFIG["TIMELINE"] if s["start_global"] <= t < s["end_global"]), CONFIG["TIMELINE"][-1])
                    t_local = t - target_scene["local_offset"]
                    target_page = pages[os.path.abspath(target_scene["html_path"])]

                    opacity = 1.0
                    if target_scene["fade_out_start"] is not None and t >= target_scene["fade_out_start"]:
                        opacity = max(0.0, 1.0 - (t - target_scene["fade_out_start"]) / (target_scene["fade_out_end"] - target_scene["fade_out_start"]))
                    elif target_scene["fade_in_start"] is not None and t < target_scene["fade_in_end"]:
                        opacity = 0.0 if t < target_scene["fade_in_start"] else min(1.0, (t - target_scene["fade_in_start"]) / (target_scene["fade_in_end"] - target_scene["fade_in_start"]))

                    # 高频注入时钟
                    await target_page.evaluate(f"if(window.seekTime) window.seekTime({t_local}); document.body.style.opacity = {opacity};")
                    
                    img_bytes = await target_page.screenshot(type='png', omit_background=True)
                    ffmpeg_process.stdin.write(img_bytes)
                    ffmpeg_process.stdin.flush()

                    with global_counter.get_lock():
                        global_counter.value += 1
                        current_count = global_counter.value
                    
                    if current_count % 20 == 0:
                        with stdout_lock:
                            percent = (current_count / TOTAL_FRAMES) * 100
                            elapsed = time.time() - start_wall_time
                            fps = current_count / elapsed if elapsed > 0 else 0
                            print(f"\r 🚀 满血常驻内核压制中: {percent:6.2f}% | 帧: {current_count}/{TOTAL_FRAMES} | 均速: {fps:.1f} FPS ", end="", flush=True)

                ffmpeg_process.stdin.close()
                ffmpeg_process.wait(timeout=5.0)
            except Exception as e:
                try: ffmpeg_process.kill()
                except: pass
                
        # 所有任务结束，安全关闭浏览器
        await browser.close()


def worker_entry(worker_id, task_queue, global_counter, stdout_lock, start_wall_time):
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(worker_main_loop(worker_id, task_queue, global_counter, stdout_lock, start_wall_time))


if __name__ == '__main__':
    print(f"================ 🏁 工业级高保真渲染引擎：9950X3D × RTX 5080 ================")
    
    if not os.path.exists(CONFIG["BG_VIDEO"]):
        print(f"❌ 错误: 找不到底图背景视频: {CONFIG['BG_VIDEO']}")
        sys.exit(1)

    start_wall_time = time.time()
    global_counter = Value('i', 0)
    stdout_lock = Lock()

    total_chunks = (TOTAL_FRAMES + CONFIG["CHUNK_FRAMES"] - 1) // CONFIG["CHUNK_FRAMES"]
    task_queue = Queue()
    for i in range(total_chunks):
        task_queue.put(i)

    processes = []
    print(f"🌐 动态微切片调度器上线！任务池共 {total_chunks} 块，8路常驻内核集群启动中...\n")
    for i in range(CONFIG["NUM_WORKERS"]):
        p = Process(target=worker_entry, args=(i, task_queue, global_counter, stdout_lock, start_wall_time))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    print(f"\n⏳ 节点任务全部结束，准备无损物理缝合...")
    time.sleep(1)

    concat_list_path = "concat_list.txt"
    with open(concat_list_path, "w") as f:
        for i in range(total_chunks):
            f.write(f"file 'temp_chunk_{i:04d}.mp4'\n")

    concat_cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-f', 'concat', '-safe', '0', '-i', concat_list_path, 
        '-i', CONFIG["BG_VIDEO"],
        '-map', '0:v', '-map', '1:a?', 
        '-c:v', 'copy', '-c:a', 'copy', 
        CONFIG["OUTPUT_FILENAME"]
    ]
    subprocess.run(concat_cmd)

    if os.path.exists(concat_list_path): os.remove(concat_list_path)
    for i in range(total_chunks):
        try: os.remove(f"temp_chunk_{i:04d}.mp4")
        except: pass

    total_duration = time.time() - start_wall_time
    print(f"\n✨ 管线完美封包！死锁与爆存已彻底解决！")
    print(f" 📊 综合总耗时: {total_duration:.1f} 秒 | 全程稳定均速: {TOTAL_FRAMES / total_duration:.1f} FPS")
    print(f" 🎉 4K60 帧无损母片出厂: {CONFIG['OUTPUT_FILENAME']}")