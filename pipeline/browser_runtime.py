"""Renderer/linter browser readiness, independent of an interactive user browser."""


async def ready(page, *, scene=True):
    await page.evaluate("async () => { await document.fonts.ready; }")
    if scene:
        count = await page.locator("#stage").count()
        runtime = await page.evaluate("typeof window.seekTime")
        if count != 1 or runtime != "function":
            raise RuntimeError("invalid scene: expected one #stage and window.seekTime")
    await page.evaluate("""async () => {
      const nodes=[...document.querySelectorAll('svg image')];
      await Promise.all(nodes.map(node => new Promise((resolve,reject) => {
        const href=node.getAttribute('href') || node.getAttribute('xlink:href');
        if (!href) {reject(new Error('empty SVG image source')); return;}
        const image=new Image(); const timer=setTimeout(()=>reject(new Error('image load timeout')),15000);
        image.onload=()=>{clearTimeout(timer);resolve();};
        image.onerror=()=>{clearTimeout(timer);reject(new Error('image failed to load: '+href));};
        image.src=href;
      })));
    }""")
