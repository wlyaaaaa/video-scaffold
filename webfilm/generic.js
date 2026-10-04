/* External capture clock. Injected by the recorder; never added to a submission. */
({seed, duration, rate}) => {
  window.__WEBFILM_TIME__ = 0;
  window.__WEBFILM_VIOLATIONS__ = [];
  window.__WEBFILM_GENERIC__ = {audioContexts: [], limitations: []};
  const evidence = window.__WEBFILM_GENERIC__;
  let now = 0, serial = 0, randomState = seed >>> 0;
  const timers = new Map(), frames = new Map();
  const epoch = 1700000000000, RealDate = Date, RealOffline = OfflineAudioContext;
  Math.random = () => {randomState=(Math.imul(randomState,1664525)+1013904223)>>>0;return randomState/4294967296;};
  // A capture seed also fixes visual randomness obtained through crypto APIs;
  // these replacements are confined to this isolated, offline recording.
  Object.defineProperty(crypto,'getRandomValues',{value:array=>{
    const bytes=new Uint8Array(array.buffer,array.byteOffset,array.byteLength);
    for(let i=0;i<bytes.length;i++)bytes[i]=Math.floor(Math.random()*256);return array;
  }});
  Object.defineProperty(crypto,'randomUUID',{value:()=>{
    const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
    const hex=[...bytes].map(byte=>byte.toString(16).padStart(2,'0')).join('');return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
  }});
  window.Date = new Proxy(RealDate, {
    construct(target,args) {return Reflect.construct(target,args.length?args:[epoch+now*1000]);},
    apply() {return new RealDate(epoch+now*1000).toString();},
    get(target,key) {return key==='now'?()=>epoch+now*1000:Reflect.get(target,key);}
  });
  Object.defineProperty(performance,'now',{value:()=>now*1000});
  try {Object.defineProperty(Event.prototype,'timeStamp',{get:()=>now*1000});} catch (_) {}
  const schedule=(repeat,callback,delay,args)=>{
    const id=++serial, seconds=Math.max(repeat?1:0, Number(delay)||0)/1000;
    timers.set(id,{id,at:now+seconds,seconds,repeat,callback,args});return id;
  };
  window.setTimeout=(callback,delay,...args)=>schedule(false,callback,delay,args);
  window.setInterval=(callback,delay,...args)=>schedule(true,callback,delay,args);
  window.clearTimeout=window.clearInterval=id=>timers.delete(id);
  window.requestAnimationFrame=callback=>{const id=++serial;frames.set(id,callback);return id;};
  window.cancelAnimationFrame=id=>frames.delete(id);
  for (const name of ['Worker','SharedWorker','AudioWorkletNode','RTCPeerConnection','WebSocket','EventSource']) {
    const original=window[name];
    if (!original) continue;
    window[name]=function(){evidence.limitations.push(name+' runs outside the supported deterministic clock');throw new Error('Unsupported deterministic API '+name);};
  }
  window.addEventListener('securitypolicyviolation', event=>{
    if(event.blockedURI && !['inline','eval'].includes(event.blockedURI)) window.__WEBFILM_VIOLATIONS__.push('Blocked request '+event.blockedURI);
  });
  const parameterClocks = new WeakMap();
  const valueDescriptor=Object.getOwnPropertyDescriptor(AudioParam.prototype,'value');
  if(valueDescriptor?.set) Object.defineProperty(AudioParam.prototype,'value',{
    ...valueDescriptor,
    set(value){if(parameterClocks.has(this)) this.setValueAtTime(value,now);else valueDescriptor.set.call(this,value);}
  });
  function captureAudio(options={}) {
    const offline=new RealOffline(2,Math.round(duration*rate),rate);
    const master=offline.createGain();master.connect(offline.destination);
    const record={offline,proxy:null,state:'running'};
    evidence.audioContexts.push(record);
    const proxy=new Proxy(offline,{
      get(target,key) {
        if(key==='currentTime')return now;
        if(key==='destination')return master;
        if(key==='state')return record.state;
        if(key==='baseLatency'||key==='outputLatency')return 0;
        if(key==='getOutputTimestamp')return ()=>({contextTime:now,performanceTime:now*1000});
        if(key==='resume')return async()=>{record.state='running';};
        if(key==='suspend')return async()=>{record.state='suspended';evidence.limitations.push('AudioContext suspend requires realtime capture for device-clock semantics');};
        if(key==='close')return async()=>{master.gain.setValueAtTime(0,now);record.state='closed';};
        if(key==='audioWorklet')return {addModule:async()=>{evidence.limitations.push('AudioWorklet');throw new Error('AudioWorklet requires realtime fallback');}};
        const value=Reflect.get(target,key,target);
        if(typeof value!=='function')return value;
        if(String(key).startsWith('create') && key!=='createBuffer' && key!=='createPeriodicWave') return (...args)=>{
          const node=value.apply(target,args);
          for(const name of ['frequency','detune','gain','Q','delayTime','pan','playbackRate','threshold','knee','ratio','attack','release']) {
            if(node[name] instanceof AudioParam) parameterClocks.set(node[name],record);
          }
          if(typeof node.start==='function') {
            const start=node.start.bind(node);node.start=(at,...args)=>start(Math.max(at===undefined?now:Number(at),now),...args);
          }
          if(typeof node.stop==='function') {
            const stop=node.stop.bind(node);node.stop=at=>stop(Math.max(at===undefined?now:Number(at),now));
          }
          if(typeof node.disconnect==='function') {
            const disconnect=node.disconnect.bind(node);node.disconnect=(...args)=>{
              if(now>0)evidence.limitations.push('Time-varying audio graph disconnection requires realtime fallback');
              return disconnect(...args);
            };
          }
          if(key==='createAnalyser') {
            evidence.limitations.push('Analyser-driven pictures require a shared precomputed audio timeline or realtime fallback');
          }
          if(['createMediaElementSource','createMediaStreamSource','createMediaStreamDestination'].includes(key)) {
            evidence.limitations.push('Device/media stream audio is not code-only offline audio');
          }
          return node;
        };
        return value.bind(target);
      }
    });
    record.proxy=proxy;
    return proxy;
  }
  const RealAudio=window.AudioContext;
  window.AudioContext=window.webkitAudioContext=captureAudio;
  captureAudio.prototype=RealAudio.prototype;
  const animationBirths=new WeakMap();
  function sampleAnimations(at) {
    document.body?.getBoundingClientRect();
    for(const animation of document.getAnimations()) {
      if(!animationBirths.has(animation))animationBirths.set(animation,at);
      animation.pause();animation.currentTime=(at-animationBirths.get(animation))*1000;
    }
  }
  window.__webfilmAdvance = async target => {
    if(target < now-1e-8)throw new Error('Generic clock is forward-only; reload the original page to seek backwards');
    let count=0;
    for(;;) {
      const due=[...timers.values()].filter(timer=>timer.at<=target+1e-9).sort((a,b)=>a.at-b.at||a.id-b.id)[0];
      if(!due)break;
      if(++count>10000)throw new Error('Too many timer callbacks in one frame');
      now=due.at;window.__WEBFILM_TIME__=now;
      if(due.repeat)due.at+=due.seconds;else timers.delete(due.id);
      if(typeof due.callback==='function')due.callback(...due.args);else (0,eval)(String(due.callback));
      await Promise.resolve();
      sampleAnimations(now);
    }
    now=target;window.__WEBFILM_TIME__=now;
    const pending=[...frames.values()];frames.clear();
    for(const callback of pending){callback(target*1000);await Promise.resolve();}
    sampleAnimations(target);
    document.documentElement.style.scrollBehavior='auto';
    document.body.getBoundingClientRect();
    await Promise.resolve();
  };
  window.__webfilmExportAudio = async () => {
    const length=Math.round(duration*rate), left=new Float32Array(length),right=new Float32Array(length);
    for(const record of evidence.audioContexts) {
      const audio=await record.offline.startRendering();
      const a=audio.getChannelData(0),b=audio.getChannelData(1);
      for(let i=0;i<length;i++){left[i]+=a[i];right[i]+=b[i];}
    }
    const bytes=new Uint8Array(44+length*4),view=new DataView(bytes.buffer);
    const ascii=(at,str)=>{for(let i=0;i<str.length;i++)bytes[at+i]=str.charCodeAt(i);};
    ascii(0,'RIFF');view.setUint32(4,36+length*4,true);ascii(8,'WAVE');ascii(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,2,true);view.setUint32(24,rate,true);view.setUint32(28,rate*4,true);view.setUint16(32,4,true);view.setUint16(34,16,true);ascii(36,'data');view.setUint32(40,length*4,true);
    let peak=0,energy=0;
    for(let i=0;i<length;i++)for(let c=0;c<2;c++){
      const value=(c===0?left:right)[i];if(!Number.isFinite(value))throw new Error('Nonfinite offline audio');
      peak=Math.max(peak,Math.abs(value));energy+=value*value;const limited=Math.max(-1,Math.min(1,value));view.setInt16(44+i*4+c*2,Math.round(limited*(limited<0?32768:32767)),true);
    }
    let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
    return {wav:btoa(binary),length,rate,channels:2,peak,rms:Math.sqrt(energy/(length*2)),clipped:peak>1,contexts:evidence.audioContexts.length,limitations:[...new Set(evidence.limitations)]};
  };
}
