async ({fps, start, end, binding, cached, verifyFrames=false, checkOnly=false, keepEncoder=false, sampleFrames=null}) => {
  let session=keepEncoder && window.__WEBFILM_ENCODER_SESSION__;
  const now=()=>Performance.prototype.now.call(performance), began=now();
  const timing={seek_ms:0,validate_ms:0,composition_ms:0,readback_ms:0,pack_ms:0,sha_ms:0,
    encode_ms:0,backpressure_ms:0,base64_ms:0,binding_ms:0,flush_ms:0};
  const unsupported=message=>{const e=new Error(message); e.name='CanvasUnsupported'; throw e;};
  const intersects=r=>r.width>0 && r.height>0 && r.right>0 && r.bottom>0 && r.left<innerWidth && r.top<innerHeight;
  const shown=n=>{const s=getComputedStyle(n); return s.display!=='none' && s.visibility==='visible' && +s.opacity!==0;};
  const noEffects=node=>{
    const s=getComputedStyle(node);
    for (const [key,value] of Object.entries({filter:'none',backdropFilter:'none',transform:'none',
      perspective:'none',clipPath:'none',maskImage:'none',mixBlendMode:'normal',boxShadow:'none',
      rotate:'none',scale:'none',translate:'none'}))
      if (s[key] && s[key]!==value) unsupported('Canvas/ancestor CSS effect: '+key);
    if (+s.opacity!==1 || s.clip!=='auto' || s.borderRadius!=='0px' ||
        ['Top','Right','Bottom','Left'].some(side=>parseFloat(s['border'+side+'Width'])!==0) ||
        (s.zoom && !['1','normal'].includes(s.zoom)) || s.contentVisibility!=='visible' ||
        (s.outlineStyle!=='none' && parseFloat(s.outlineWidth)>0)) unsupported('Canvas/ancestor CSS clipping or drawing effect');
    const r=node.getBoundingClientRect();
    if ((s.overflowX!=='visible' || s.overflowY!=='visible') &&
        (r.left>0 || r.top>0 || r.right<innerWidth || r.bottom<innerHeight)) unsupported('Ancestor clips viewport');
    return s;
  };
  let composed=session?.composed, compositor=session?.compositor, contextTypes=new Set(), usedComposition=false;
  const validate=()=>{
    if (document.fullscreenElement || document.querySelector(':modal, :popover-open') ||
        document.getAnimations().some(a=>a.effect?.pseudoElement?.startsWith('::view-transition')))
      unsupported('Top-layer or view-transition painting');
    const visible=[...document.querySelectorAll('canvas')].filter(n=>shown(n)&&intersects(n.getBoundingClientRect()));
    if (visible.length!==1) unsupported('Requires a single visible full-viewport canvas');
    const canvas=visible[0], r=canvas.getBoundingClientRect(), record=window.__WEBFILM_CANVAS_CONTEXTS__?.get(canvas);
    if (r.left!==0 || r.top!==0 || r.width!==innerWidth || r.height!==innerHeight ||
        canvas.width!==innerWidth || canvas.height!==innerHeight || devicePixelRatio!==1)
      unsupported('Canvas bitmap/CSS size must exactly equal viewport at device scale 1');
    if (!record || !['2d','webgl','webgl2','experimental-webgl'].includes(record.type))
      unsupported('Canvas requires a recorded existing 2D/WebGL context');
    const context=record.context, attributes=context.getContextAttributes();
    if (!attributes || context.isContextLost?.() || (record.type==='2d' && attributes.colorSpace!=='srgb') ||
        (context.drawingBufferColorSpace && context.drawingBufferColorSpace!=='srgb')) unsupported('Requires live sRGB canvas context');
    contextTypes.add(record.type);
    const ancestors=new Set(), backgrounds=[];
    for(let n=canvas;n;n=n.parentElement) {ancestors.add(n); backgrounds.unshift([n,noEffects(n)]);}
    const style=backgrounds[backgrounds.length-1][1];
    if (['Top','Right','Bottom','Left'].some(side=>parseFloat(style['padding'+side])!==0) ||
        style.objectFit!=='fill' || style.objectPosition!=='50% 50%') unsupported('Canvas padding or object positioning');
    for(const n of document.querySelectorAll('*')) {
      if (!shown(n)) continue;
      if (n.shadowRoot || !ancestors.has(n)) unsupported('Additional visible DOM cannot be proven canvas-only');
      for(const pseudo of ['::before','::after','::marker']) {
        const s=getComputedStyle(n,pseudo);
        if(s.content && !['none','normal'].includes(s.content) && s.display!=='none') unsupported('Visible generated content');
      }
      if(n!==canvas) for(const child of n.childNodes) if(child.nodeType===Node.TEXT_NODE && child.textContent.trim()) {
        const range=document.createRange(); range.selectNodeContents(child);
        if([...range.getClientRects()].some(intersects)) unsupported('Visible DOM text outside canvas');
      }
    }
    if(attributes.alpha===false) return canvas;
    if(backgrounds[0][1].colorScheme?.includes('dark')) unsupported('Transparent dark page has no proven base color');
    const at=now();
    if(!composed) {composed=new OffscreenCanvas(innerWidth,innerHeight); compositor=composed.getContext('2d',{alpha:false,colorSpace:'srgb'}); if(keepEncoder){session.composed=composed; session.compositor=compositor;}}
    compositor.fillStyle='#fff'; compositor.fillRect(0,0,innerWidth,innerHeight);
    for(const [node,s] of backgrounds) {
      if(s.backgroundImage!=='none') unsupported('Transparent canvas requires solid page backgrounds');
      if(s.backgroundClip!=='border-box') unsupported('Transparent canvas background clipping is unsupported');
      const r=node.getBoundingClientRect();
      const propagated=node.tagName==='BODY' && backgrounds[0][1].backgroundColor==='rgba(0, 0, 0, 0)';
      if(node.tagName!=='HTML' && !propagated && s.backgroundColor!=='rgba(0, 0, 0, 0)' &&
          (r.left>0||r.top>0||r.right<innerWidth||r.bottom<innerHeight)) unsupported('Background does not cover viewport');
      compositor.fillStyle=s.backgroundColor; compositor.fillRect(0,0,innerWidth,innerHeight);
    }
    compositor.drawImage(canvas,0,0); usedComposition=true; timing.composition_ms+=now()-at;
    return composed;
  };
  const seek=async i=>{
    // Await host checks before drawing: a WebGL drawing buffer can clear when
    // a binding yields to the event loop before VideoFrame snapshots it.
    if((i-start)%Math.max(1,Math.round(fps))===0) {
      const errors=window.__WEBFILM_VIOLATIONS__||[];
      if(errors.length) throw Error('Work runtime violations: '+errors.join('; '));
      await window[binding]({kind:'check'});
    }
    const at=now(), t=i/fps; window.__WEBFILM_TIME__=t; await window.webfilm.render(t);
    for(const a of document.getAnimations()) {a.pause(); a.currentTime=t*1000;}
    document.documentElement.style.scrollBehavior='auto'; document.body.getBoundingClientRect(); timing.seek_ms+=now()-at;
    const checked=now(), canvas=validate(); timing.validate_ms+=now()-checked;
    const frame=new VideoFrame(canvas,{timestamp:stamp(i),duration:stamp(i+1)-stamp(i)});
    if(!frameInfo) frameInfo={format:frame.format,color_space:frame.colorSpace?.toJSON?.()||null};
    return frame;
  };
  let encoder, failure, writes=Promise.resolve(), wake, support, pending=0, frameInfo, decoderColorSpace, batch=[], completed=false;
  const originFrame=session?.originFrame??start, frames=[], indices=[], timestamps=[], stamp=i=>Math.round((i-originFrame)*1e6/fps);
  const samples=new Set(sampleFrames ?? [start,Math.floor((start+end)/2),end-1]), check=()=>{if(failure)throw failure;};
  const hash=async frame=>{
    let at=now(); const options={format:'RGBA',colorSpace:'srgb'}, rgba=new Uint8Array(frame.allocationSize(options));
    const [layout]=await frame.copyTo(rgba,options); timing.readback_ms+=now()-at; at=now();
    const width=innerWidth,height=innerHeight,rgb=new Uint8Array(width*height*3); let b=0;
    for(let y=0;y<height;y++) for(let a=layout.offset+y*layout.stride,limit=a+width*4;a<limit;a+=4) {
      if(rgba[a+3]!==255) unsupported('Encoded sample contains transparent pixels');
      rgb[b++]=rgba[a]; rgb[b++]=rgba[a+1]; rgb[b++]=rgba[a+2];
    }
    timing.pack_ms+=now()-at; at=now(); const digest=await crypto.subtle.digest('SHA-256',rgb); timing.sha_ms+=now()-at;
    return [...new Uint8Array(digest)].map(n=>n.toString(16).padStart(2,'0')).join('');
  };
  // framerate is optional rate-control guidance; Chrome 154 rejects 4K60 with
  // this hint. Input timestamps and durations still specify the exact fps.
  const config={codec:'avc1.640034',width:innerWidth,height:innerHeight,bitrate:120000000,
    latencyMode:'quality',hardwareAcceleration:'prefer-hardware',avc:{format:'annexb'}};
  const send=()=>{
    if(!batch.length)return;
    const chunks=batch; batch=[]; const bytes=new Uint8Array(chunks.reduce((n,c)=>n+c.bytes.length,0)); let at=0;
    for(const c of chunks){bytes.set(c.bytes,at); at+=c.bytes.length;} pending++;
    writes=writes.then(async()=>{
      for(let offset=0,part=0;offset<bytes.length;offset+=262144,part++) {
        let at=now(), slice=bytes.subarray(offset,offset+262144), data;
        if(slice.toBase64) data=slice.toBase64();
        else {let binary=''; for(let j=0;j<slice.length;j+=32768)binary+=String.fromCharCode(...slice.subarray(j,j+32768)); data=btoa(binary);}
        timing.base64_ms+=now()-at; at=now();
        await window[binding]({kind:'chunk',timestamps:part?[]:chunks.map(c=>c.timestamp),data}); timing.binding_ms+=now()-at;
      }
    }).catch(e=>{failure=e; wake?.();}).finally(()=>{pending--; wake?.();});
  };
  const dispatch={error:e=>{failure=e; wake?.();},output:(chunk,metadata)=>{
      try {
        decoderColorSpace=metadata?.decoderConfig?.colorSpace||decoderColorSpace;
        const i=timestamps.length;
        if(i>=end-start || chunk.timestamp!==stamp(start+i)) throw Error('Encoder output timestamps/count differ from inputs');
        timestamps.push(chunk.timestamp); const bytes=new Uint8Array(chunk.byteLength); chunk.copyTo(bytes);
        batch.push({timestamp:Math.round(i*1e6/fps),bytes}); if(batch.length===8)send();
      } catch(e) {failure=e; wake?.();}
    }};
  const initialize=async()=>{
    if(session) {encoder=session.encoder; support=session.support; decoderColorSpace=session.colorSpace; session.dispatch=dispatch; return;}
    if(!window.VideoEncoder||!window.VideoFrame) unsupported('WebCodecs encoder unavailable');
    support=await VideoEncoder.isConfigSupported(config);
    if(!support.supported) unsupported('H264 prefer-hardware configuration unsupported');
    session={originFrame,support,dispatch};
    encoder=new VideoEncoder({error:e=>session.dispatch.error(e),output:(...args)=>session.dispatch.output(...args)});
    session.encoder=encoder; encoder.configure(config); if(keepEncoder)window.__WEBFILM_ENCODER_SESSION__=session;
  };
  const encode=async (frame,index)=>{
    let at=now(); check();
    while(encoder.encodeQueueSize>=8||pending>=8) {
      await new Promise(resolve=>{wake=resolve; encoder.addEventListener('dequeue',resolve,{once:true});}); wake=null; check();
    }
    timing.backpressure_ms+=now()-at; at=now(); encoder.encode(frame,{keyFrame:index===start}); timing.encode_ms+=now()-at; check();
  };
  try {
    if(!verifyFrames) cached=null;
    if(!cached) await initialize();
    for(let i=start;i<end;i++) {
      check(); const frame=await seek(i);
      try {
        let digest;
        if(verifyFrames||samples.has(i)) {digest=await hash(frame); frames.push(digest); indices.push(i);}
        if(!encoder && digest!==cached[i-start]) {
          await initialize();
          for(let prior=start;prior<i;prior++) {
            const replay=await seek(prior);
            try {if(await hash(replay)!==frames[prior-start])throw Error('Absolute-time redraw changed pixels'); await encode(replay,prior);}
            finally {replay.close();}
          }
        }
        if(encoder) await encode(frame,i);
      } finally {frame.close();}
    }
    if(encoder) {const at=now(); await encoder.flush(); send(); await writes; check(); timing.flush_ms+=now()-at;}
    if(encoder && timestamps.length!==end-start)throw Error('Encoder did not output every input frame');
    timing.total_ms=now()-began; completed=true; if(session)session.colorSpace=decoderColorSpace;
    return {frames,frame_indices:indices,reused:!encoder,timing,evidence:{requested_config:config,
      supported_config:support?.config||null,support_confirmed:support?.supported||false,pixel_format:'RGB24',
      color_space:'srgb',opaque:true,context_types:[...contextTypes],alpha_composed:usedComposition,
      first_video_frame:frameInfo,decoder_color_space:decoderColorSpace||null,
      sampled:!verifyFrames,timestamp_origin_frame:start,encoder_origin_frame:originFrame,frame_duration_rule:'difference of rounded microsecond timestamps'}};
  } catch(e) {if(e.name==='CanvasUnsupported')return {unsupported:e.message}; throw e;}
  finally {if((!keepEncoder||!completed) && encoder && encoder.state!=='closed')encoder.close();
    if(!completed && keepEncoder)delete window.__WEBFILM_ENCODER_SESSION__; await writes;}
}
