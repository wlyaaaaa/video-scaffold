"""Self-contained original code works, written only into a new isolated folder."""
from __future__ import annotations

import json
from pathlib import Path
import shutil


PROMPT = """请用原创网页代码做一段20秒的完整动画：米白纸纹、水彩感背景、手绘线条，一只有性格的小鸟落地苏醒，穿过草地，飞上星空，再返回写出 wly0829.cn。画面要连贯，音乐包含旋律、低音、轻打击和飞行音效。全部由代码生成，不联网，不用预录音视频或视频生成模型；普通 Chrome 可以直接播放，声音点击解锁，同一代码也支持按绝对时间逐帧捕获与离线双声道音频。"""

_STYLE = """
html,body{margin:0;min-height:100%;background:#f3eddd;color:#293e35}
body{font-family:Georgia,'Times New Roman','Microsoft YaHei',serif}
canvas{display:block;width:100vw;height:100vh}
*{box-sizing:border-box}
"""

# Every drawable value comes from t or a fixed seed. No external images or fonts.
_PAINTER = r"""
const canvas=document.getElementById('scene');
const ctx=canvas.getContext('2d');
const W=1920,H=1080,TAU=Math.PI*2;
const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x));
const smooth=x=>{x=clamp(x);return x*x*(3-2*x);};
const mix=(a,b,t)=>a+(b-a)*t;
function random(seed){let s=seed>>>0;return ()=>{s=(Math.imul(s,1664525)+1013904223)>>>0;return s/4294967296;};}
const paper=document.createElement('canvas');paper.width=W*2;paper.height=H*2;
const pc=paper.getContext('2d'),grain=random(829);
pc.fillStyle='#f4eedf';pc.fillRect(0,0,paper.width,paper.height);
for(let i=0;i<124000;i++){
  const v=grain();pc.fillStyle=v>.52?'rgba(117,91,46,.025)':'rgba(255,255,250,.22)';
  const x=grain()*paper.width,y=grain()*paper.height;pc.fillRect(x,y,.4+grain()*2.5,.4+grain()*1.7);
}
for(let i=0;i<95;i++){
  const x=grain()*paper.width,y=grain()*paper.height,r=100+grain()*300;
  const g=pc.createRadialGradient(x,y,0,x,y,r);
  g.addColorStop(0,'rgba(139,105,51,.022)');g.addColorStop(1,'rgba(139,105,51,0)');
  pc.fillStyle=g;pc.fillRect(x-r,y-r,2*r,2*r);
}
const stars=Array.from({length:135},()=>({x:grain()*W,y:grain()*H*.86,r:1+grain()*3,phase:grain()*TAU}));
function wash(x,y,rx,ry,color,seed=0,alpha=1){
  ctx.save();const base=ctx.globalAlpha*alpha;
  const rng=random(seed+311);ctx.fillStyle=color;
  for(let layer=0;layer<3;layer++){
    ctx.globalAlpha=base*(layer===0?.15:.075);ctx.beginPath();
    for(let k=0;k<181;k++){
      const a=k*TAU/180,rad=1+Math.sin(a*5+seed)*.018+Math.sin(a*9+layer)*.012+(rng()-.5)*.014;
      const px=x+Math.cos(a)*rx*rad,py=y+Math.sin(a)*ry*rad;
      if(k===0)ctx.moveTo(px,py);else ctx.lineTo(px,py);
    }ctx.closePath();ctx.fill();
  }ctx.restore();
}
function ink(points,color='#334c42',width=3){
  ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineCap='round';ctx.lineJoin='round';ctx.beginPath();
  points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();
}
function oval(x,y,rx,ry,fill,stroke=null,width=3){
  ctx.beginPath();ctx.ellipse(x,y,rx,ry,0,0,TAU);ctx.fillStyle=fill;ctx.fill();
  if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=width;ctx.stroke();}
}
function leaf(x,y,length,angle,color){
  ctx.save();ctx.translate(x,y);ctx.rotate(angle);ctx.fillStyle=color;ctx.beginPath();
  ctx.moveTo(0,0);ctx.bezierCurveTo(-length*.4,-length*.3,-length*.22,-length*.8,0,-length);
  ctx.bezierCurveTo(length*.2,-length*.7,length*.3,-length*.3,0,0);ctx.fill();ctx.restore();
}
function hill(y,height,color,phase,t){
  ctx.fillStyle=color;ctx.beginPath();ctx.moveTo(-80,H);
  for(let x=-80;x<W+100;x+=24){ctx.lineTo(x,y+Math.sin(x*.0026+phase)*height+Math.sin(x*.007+phase)*height*.18);}
  ctx.lineTo(W+100,H);ctx.closePath();ctx.fill();
}
function flower(x,y,scale,t,seed){
  const sway=Math.sin(t*1.3+seed)*8;ctx.save();ctx.translate(x,y);ctx.scale(scale,scale);
  ctx.strokeStyle='#697d50';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(0,0);ctx.quadraticCurveTo(sway-12,-45,sway,-93);ctx.stroke();
  leaf(-2,-30,34,-.9,'#809058');leaf(1,-58,28,.8,'#a0a35b');
  ctx.translate(sway,-93);const petals=seed%3===0?'#cf806f':seed%3===1?'#e3bf70':'#efdfbc';
  for(let i=0;i<5;i++){const a=i*TAU/5;oval(Math.cos(a)*14,Math.sin(a)*14,11,15,petals);}
  oval(0,0,8,8,'#9d7846');ctx.restore();
}
function meadow(t,alpha){
  ctx.save();ctx.globalAlpha=alpha;
  wash(490,545,750,290,'#bad0b1',3,.8);wash(1410,725,720,255,'#b7c59b',7,.75);
  ctx.globalAlpha=alpha*.18;hill(788,80,'#8aa88f',1.3,t);ctx.globalAlpha=alpha*.24;hill(835,60,'#87a06d',2.6,t);
  ctx.globalAlpha=alpha*.4;hill(895,45,'#a1ab71',.3,t);ctx.globalAlpha=alpha;
  const r=random(392);for(let i=0;i<135;i++){
    const x=r()*W,y=855+r()*155,h=12+r()*44,sway=Math.sin(t*1.1+x)*5;
    ink([[x,y],[x+sway,y-h],[x+sway+4,y-h+8]],i%2?'#87986666':'#496b4d55',1.5);
  }
  for(let i=0;i<20;i++)flower(45+i*99,918+(i%3)*15,.6+(i%4)*.13,t,i);
  ctx.globalAlpha=alpha*.65;
  for(let i=0;i<7;i++){
    const x=330+i*205+Math.sin(t*.7+i)*40,y=590+Math.cos(t*.9+i*2)*55;
    oval(x,y,3.5,3.5,'#f8e6a8');
  }
  ctx.restore();
}
function star(x,y,size,color,alpha=1){
  ctx.save();ctx.translate(x,y);ctx.globalAlpha*=alpha;ctx.fillStyle=color;ctx.beginPath();
  for(let i=0;i<10;i++){const a=i*Math.PI/5-Math.PI/2,r=i%2?size*.42:size;
    i?ctx.lineTo(Math.cos(a)*r,Math.sin(a)*r):ctx.moveTo(Math.cos(a)*r,Math.sin(a)*r);}
  ctx.closePath();ctx.fill();ctx.restore();
}
function night(t,amount){
  if(amount<=0)return;ctx.save();ctx.globalAlpha=amount;
  const sky=ctx.createLinearGradient(0,0,0,H);sky.addColorStop(0,'#162a43');sky.addColorStop(.6,'#3b5363');sky.addColorStop(1,'#88848f');
  ctx.fillStyle=sky;ctx.fillRect(0,0,W,H);
  wash(720,440,900,270,'#8cacb2',48,.36);wash(1330,910,800,400,'#b29cb3',91,.24);
  for(const s of stars)star(s.x,s.y,s.r,'#f3eed7',.35+.5*(.5+.5*Math.sin(t*2+s.phase)));
  ctx.save();ctx.translate(1450,240);ctx.rotate(-.25);
  const glow=ctx.createRadialGradient(0,0,20,0,0,180);glow.addColorStop(0,'#fff1ba55');glow.addColorStop(1,'#fff1ba00');
  ctx.fillStyle=glow;ctx.fillRect(-180,-180,360,360);ctx.fillStyle='#f8e8b9';ctx.beginPath();
  ctx.moveTo(30,-93);ctx.bezierCurveTo(-116,-67,-118,88,25,99);ctx.bezierCurveTo(-50,48,-32,-54,30,-93);ctx.fill();ctx.restore();
  star(1075,262,30,'#efce83',.8+.2*Math.sin(t*3));
  ctx.restore();
}
function bird(x,y,t,scale=1,flying=false,sleeping=false,rotation=0){
  ctx.save();ctx.translate(x,y);ctx.rotate(rotation);
  const breathe=1+Math.sin(t*3)*.015;ctx.scale(scale*breathe,scale/breathe);
  // Three uneven tail feathers and a little neck scarf keep the silhouette personal.
  leaf(-50,25,71,-1.15,'#687e80');leaf(-49,32,62,-1.55,'#92a29b');leaf(-47,35,50,-1.8,'#b6b891');
  ctx.strokeStyle='#344d44';ctx.lineWidth=4;
  ctx.fillStyle='#d6a06b';ctx.beginPath();ctx.moveTo(-68,28);
  ctx.bezierCurveTo(-83,-24,-41,-89,20,-88);ctx.bezierCurveTo(87,-89,105,-14,67,42);
  ctx.bezierCurveTo(23,86,-50,78,-68,28);ctx.fill();ctx.stroke();
  wash(14,-15,80,72,'#b6744f',24,.48);oval(16,32,39,29,'#f1dabc');
  // The wing rotates around its root instead of advancing frame by frame.
  ctx.save();ctx.translate(-33,3);ctx.rotate(flying?-.75+Math.sin(t*24)*.65:.16+Math.sin(t*4)*.08);
  ctx.fillStyle='#758d8b';ctx.beginPath();ctx.moveTo(0,-14);ctx.bezierCurveTo(-28,-28,-57,14,-41,48);
  ctx.bezierCurveTo(-12,56,17,25,0,-14);ctx.fill();ctx.stroke();
  ink([[-22,8],[-34,29]],'#465f5c',2);ink([[-12,14],[-22,37]],'#465f5c',2);ctx.restore();
  oval(43,-27,17,23,'#fff6dc');oval(8,-29,15,21,'#fff6dc');
  const blink=sleeping||Math.sin(t*2.7)>.988;
  if(blink){ink([[-2,-26],[8,-22],[18,-26]],'#364637',3);ink([[31,-23],[43,-19],[55,-24]],'#364637',3);}
  else{oval(13,-27,5.5,8,'#334536');oval(48,-25,6,8,'#334536');oval(14,-30,1.7,2,'#fff8ed');oval(49,-28,2,2,'#fff8ed');}
  ctx.fillStyle='#cc784b';ctx.beginPath();ctx.moveTo(65,-7);ctx.lineTo(86,-1);ctx.lineTo(65,6);ctx.closePath();ctx.fill();
  oval(40,4,13,7,'#cc877b66');
  ctx.fillStyle='#be6c5f';ctx.beginPath();ctx.moveTo(-8,46);ctx.lineTo(51,43);ctx.lineTo(56,53);ctx.lineTo(-7,57);ctx.closePath();ctx.fill();
  ctx.save();ctx.translate(-1,53);ctx.rotate(Math.sin(t*6)*.2);ctx.fillStyle='#ce8270';ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(-31,34);ctx.lineTo(-35,21);ctx.lineTo(-47,27);ctx.lineTo(-27,-4);ctx.fill();ctx.restore();
  if(!flying){ink([[2,65],[4,81],[-8,83]],'#695d3f',4);ink([[35,62],[36,79],[50,81]],'#695d3f',4);}
  else{ink([[6,65],[-3,72],[9,73]],'#695d3f',3);ink([[37,62],[26,70],[40,69]],'#695d3f',3);}
  ctx.restore();
}
function lettering(t,opacity=1){
  ctx.save();ctx.globalAlpha=opacity;
  ctx.fillStyle='#345448';ctx.font='italic 146px Georgia,serif';ctx.textAlign='center';
  const title='wly0829.cn',n=Math.min(title.length,Math.floor(Math.max(0,t-16.4)*5.2));
  ctx.fillText(title.slice(0,n),W/2,570);
  const extent=clamp((t-16.9)/1.7);ctx.strokeStyle='#365747';ctx.lineWidth=4.5;ctx.lineCap='round';ctx.beginPath();
  ctx.moveTo(475,605);ctx.bezierCurveTo(700,630,1100,635,475+extent*965,615);ctx.stroke();
  ctx.globalAlpha=opacity*smooth((t-18)/.7);ctx.fillStyle='#6b7e67';ctx.font='25px Georgia,"Microsoft YaHei",serif';ctx.fillText('把好奇心，带回日常。',W/2,699);
  ctx.font='15px system-ui';ctx.letterSpacing='5px';ctx.fillText('EVERY FRAME, EVERY NOTE — MADE IN CODE',W/2,763);ctx.restore();
}
function paint(time,kind='animation',duration=20){
  const t=clamp(Number(time)||0,0,duration);
  const width=Math.max(1,innerWidth),height=Math.max(1,innerHeight);
  if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}
  ctx.setTransform(width/W,0,0,height/H,0,0);ctx.clearRect(0,0,W,H);ctx.drawImage(paper,0,0,W,H);
  if(kind==='cover'){
    wash(890,510,680,430,'#bfd0ac',23,.6);meadow(5,.7);
    ctx.fillStyle='#355649';ctx.font='italic 154px Georgia,serif';ctx.textAlign='left';ctx.fillText('A little journey.',190,367);
    ctx.font='32px Georgia,"Microsoft YaHei",serif';ctx.fillText('从一张纸，到一片星空。',203,440);
    bird(1325,650,3,2.5,false,false,-.1);ctx.font='23px Georgia,serif';ctx.fillText('wly0829.cn',207,856);
    ctx.font='15px system-ui';ctx.fillText('原创代码动画 · 20 秒',207,903);return;
  }
  if(kind==='opener'){
    const enter=smooth(t/1.1);wash(970,530,620*enter,360*enter,'#b2c6a7',21,.7);
    bird(450+enter*180,675-Math.sin(t*3)*12,t,1.55,false,t<1);
    ctx.save();ctx.globalAlpha=enter;ctx.fillStyle='#345448';ctx.font='italic 108px Georgia,serif';ctx.fillText('wly0829.cn',850,565);
    ctx.font='27px Georgia,"Microsoft YaHei",serif';ctx.fillText('今天，带着好奇心出发。',861,632);ctx.restore();return;
  }
  if(kind==='outro'){
    wash(975,550,800,320,'#c1ceb0',67,.5);bird(1420,727,t+16,1.05,false,false,-.1);
    lettering(16.4+t,1);return;
  }
  if(kind==='card'){
    wash(1100,560,650,390,'#c1d1ba',73,.62);bird(1510,790,t,1.4,false,false);
    ctx.fillStyle='#819270';ctx.font='20px system-ui';ctx.fillText('一个小想法 / 01',205,204);
    ctx.fillStyle='#325444';ctx.font='64px Georgia,"Microsoft YaHei",serif';ctx.fillText('把一步，走成一段旅程。',202,324);
    const items=[['01','先让画面有一个主角','观众有了目光的落点。'],['02','让每一步都有原因','起身、探索、飞行、返回。'],['03','给结尾留一口呼吸','画面与音乐一起落地。']];
    items.forEach((item,i)=>{ctx.save();ctx.globalAlpha=smooth((t-i*1.5-.4)/.7);const y=470+i*144;
      ctx.fillStyle='#b58161';ctx.font='italic 43px Georgia,serif';ctx.fillText(item[0],216,y);ctx.fillStyle='#3d5a49';ctx.font='31px Georgia,"Microsoft YaHei",serif';ctx.fillText(item[1],311,y-3);
      ctx.fillStyle='#77866e';ctx.font='24px Georgia,"Microsoft YaHei",serif';ctx.fillText(item[2],313,y+47);ctx.restore();});return;
  }
  const meadowAlpha=smooth((t-.8)/1.8)*(1-smooth((t-8.8)/1.4))*(1-smooth((t-15.5)/1));
  const nightAlpha=smooth((t-9)/1.3)*(1-smooth((t-14.7)/1.7));
  wash(490,430,600,320,'#e9c798',6,(1-nightAlpha)*.42);
  if(t<10.2)meadow(t,meadowAlpha);
  night(t,nightAlpha);
  const landing=smooth((t-.55)/1.1),walk=smooth((t-4)/4.2),launch=smooth((t-8.2)/1.2);
  let x=570+walk*680,y=mix(-160,780,landing),rotation=0,flying=false;
  if(t>1.6&&t<2.4)y-=Math.sin((t-1.6)/.8*Math.PI)*24;
  if(t>4&&t<8.7)y+=Math.sin(t*14)*10;
  if(t>8.2){flying=true;x=mix(1250,900,smooth((t-9)/4));y=mix(790,350,launch)-Math.sin((t-9)*1.3)*55;rotation=-.2+Math.sin(t*2)*.08;}
  if(t>14){const back=smooth((t-14)/2.4);x=mix(900,1390,back);y=mix(350,732,back);rotation=mix(-.2,0,back);flying=back<.98;}
  if(flying){
    ctx.save();const amount=nightAlpha*.6;
    for(let i=0;i<17;i++){
      const d=i*21,trailX=x-d*.58,trailY=y+d*.65+Math.sin(t*3+i)*10;
      star(trailX,trailY,5+(i%3),i%2?'#efd292':'#c2d6d0',amount*(1-i/18));
    }ctx.restore();
  }
  if(!flying&&t<9){ctx.save();ctx.globalAlpha=.12*landing;oval(x,872,99,10,'#546b44');ctx.restore();}
  bird(x,y,t,t>16?1.1:1.05,flying,t<2.7,rotation);
  if(t>3&&t<4.2){ctx.fillStyle='#7d8667';ctx.font='italic 31px Georgia,serif';ctx.fillText('hmm?',x+88,y-108);}
  if(t>7&&t<9){
    const bx=1360+Math.sin(t*3)*25,by=630-Math.sin(t*2)*22;
    ctx.save();ctx.translate(bx,by);ctx.rotate(Math.sin(t*6)*.2);oval(-11,-3,13,8,'#d6b78e');oval(11,-3,13,8,'#c98775');ink([[0,-9],[0,9]],'#786b48',2);ctx.restore();
  }
  if(t>15.5){
    wash(890,525,670,280,'#c5ceb0',31,smooth((t-15.5)/1.2)*.6);lettering(t,smooth((t-16)/.6));
    const splats=random(772);ctx.save();ctx.globalAlpha=smooth((t-17.8)/1.2);
    for(let i=0;i<28;i++){const sx=365+splats()*1230,sy=310+splats()*120;oval(sx,sy,2+splats()*6,2+splats()*5,i%2?'#aabc9366':'#c88b7066');}ctx.restore();
  }
  if(t<16){
    ctx.save();ctx.globalAlpha=(1-nightAlpha*.2)*smooth(t/.9)*(1-smooth((t-15)/.8));ctx.fillStyle=nightAlpha>.55?'#efe7ce':'#536c57';
    ctx.font='17px system-ui';ctx.letterSpacing='3px';ctx.fillText('A LITTLE JOURNEY',142,145);
    ctx.font='30px Georgia,"Microsoft YaHei",serif';ctx.letterSpacing='0px';
    const caption=t<4.5?'先醒来，再出发。':t<8.8?'草叶之间，也有远方。':'向上，遇见一颗星。';ctx.fillText(caption,145,965);
    ctx.font='italic 22px Georgia,serif';ctx.fillText(t<4.5?'wake & wonder':t<8.8?'follow the small things':'a sky full of possibilities',145,1006);ctx.restore();
  }
  // A transparent paper pass carries the same handmade surface into the night.
  ctx.save();ctx.globalAlpha=.09;ctx.globalCompositeOperation='soft-light';ctx.drawImage(paper,0,0,W,H);ctx.restore();
}
"""

_AUDIO = r"""
function score(ctx,duration){
  const master=ctx.createGain();master.gain.setValueAtTime(2,0);
  master.gain.setValueAtTime(2,Math.max(0,duration-.9));master.gain.linearRampToValueAtTime(0,duration);master.connect(ctx.destination);
  function tone(midi,at,length,volume,type='sine',pan=0){
    if(at>=duration)return;length=Math.min(length,duration-at);const osc=ctx.createOscillator(),gain=ctx.createGain(),stereo=ctx.createStereoPanner();
    osc.type=type;osc.frequency.setValueAtTime(440*Math.pow(2,(midi-69)/12),at);
    gain.gain.setValueAtTime(0,at);gain.gain.linearRampToValueAtTime(volume,at+.018);gain.gain.exponentialRampToValueAtTime(.0001,at+Math.max(.025,length));
    stereo.pan.setValueAtTime(pan,at);osc.connect(gain);gain.connect(stereo);stereo.connect(master);osc.start(at);osc.stop(at+length+.02);
  }
  const melody=[74,78,81,78,76,74,71,69,74,78,83,81,78,76,74,69,78,81,86,83,81,78,76,74,71,74,78,81,78,76,74,74];
  const beat=.5;
  for(let i=0;i<duration/beat;i++){
    const at=i*beat,midi=melody[i%melody.length],night=at>=9&&at<15;
    tone(midi+(night?12:0),at,.8,night?.09:.12,'sine',Math.sin(i)*.25);
    tone(midi+12,at+.012,.37,.025,'triangle',-.2);
    if(i%2===0)tone([50,47,55,57][Math.floor(i/8)%4],at,.78,.15,'sine',0);
    if(i%4===0){const chord=[62,66,69];chord.forEach((m,j)=>tone(m,at+j*.06,1.7,.035,'triangle',(j-1)*.3));}
  }
  // Deterministic brush percussion, with the same buffer in live and offline audio.
  const rng=random(829),noise=ctx.createBuffer(1,Math.ceil(ctx.sampleRate*.09),ctx.sampleRate),samples=noise.getChannelData(0);
  for(let i=0;i<samples.length;i++)samples[i]=(rng()*2-1)*Math.pow(1-i/samples.length,2);
  for(let at=.25;at<duration-.2;at+=.5){
    const src=ctx.createBufferSource(),filter=ctx.createBiquadFilter(),gain=ctx.createGain();src.buffer=noise;filter.type='highpass';filter.frequency.value=2100;gain.gain.setValueAtTime(.042,at);
    src.connect(filter);filter.connect(gain);gain.connect(master);src.start(at);
  }
  if(duration>10){
    for(const at of [8.4,9,14.3]){
      const osc=ctx.createOscillator(),gain=ctx.createGain();osc.type='sine';osc.frequency.setValueAtTime(at<10?340:1100,at);osc.frequency.exponentialRampToValueAtTime(at<10?1500:420,at+.55);
      gain.gain.setValueAtTime(0,at);gain.gain.linearRampToValueAtTime(.07,at+.12);gain.gain.exponentialRampToValueAtTime(.0001,at+.65);osc.connect(gain);gain.connect(master);osc.start(at);osc.stop(at+.7);
    }
  }
}
"""

_INTERACTIVE = r"""
<main>
  <header><span>WLY0829 / 小小的交互花园</span><a href="#garden">去花园看看 ↓</a></header>
  <section class="hero"><div class="copy"><small>让好奇心，动一下。</small><h1>把一颗种子<br>交给下一秒。</h1><p>移动光点，按下按钮，再向下走。<br>有些变化，就从一次轻轻的点击开始。</p><button id="button">种下一朵花 <span>↗</span></button><div id="status" aria-live="polite">今天的花园还在等待。</div></div>
  <div class="drawing" id="drawing"><span class="sun"></span><span class="stem"></span><span class="leaf a"></span><span class="leaf b"></span><span class="bloom">✿</span><i class="ground"></i><b class="spark">✧</b></div></section>
  <section id="garden"><small>第二站 / 继续向下</small><h2>一步，一朵，一片。</h2><p>用很小的动作，留下看得见的回应。</p><div class="garden-grid"><article id="hover-card" tabindex="0"><span>01 / HOVER</span><h3>停一停。</h3><p>叶片会回应你的目光。</p><div class="leaflet">❧</div></article><article><span>02 / GROW</span><h3>再长一点。</h3><p>变化无需很大，方向可以很清楚。</p><div class="leaflet">✺</div></article><article><span>03 / RETURN</span><h3>带回日常。</h3><p>wly0829.cn</p><div class="leaflet">✧</div></article></div></section>
  <footer>一个可以触碰的小花园。<span>每个动作，都有回声。</span></footer>
</main>
<style>
body{background:#f2eddf;font-family:Georgia,'Microsoft YaHei',serif;color:#325444}header{display:flex;justify-content:space-between;align-items:center;padding:36px 6vw;border-bottom:1px solid #87977430;font:15px system-ui;letter-spacing:1px}a{color:inherit;text-decoration:none}.hero{min-height:820px;height:calc(100vh - 90px);display:grid;grid-template-columns:1fr 1fr;align-items:center;padding:50px 8vw;gap:60px}.copy small,#garden>small{font:16px system-ui;letter-spacing:3px;color:#8a9575}h1{font-size:clamp(55px,5.7vw,116px);line-height:1.22;font-weight:400;margin:30px 0}p{font-size:22px;line-height:1.9;color:#75836b}#button{margin-top:18px;padding:18px 26px;background:#3c6650;border:0;border-radius:36px;color:#faf4de;font:18px Georgia,'Microsoft YaHei',serif;cursor:pointer;min-width:220px;text-align:left}#button span{float:right}#button:hover{background:#66825c}#status{margin-top:20px;font-size:16px;color:#7f8a72}.drawing{position:relative;height:500px;--grow:0;transform:translateY(calc(var(--breathe,0)*1px))}.sun{position:absolute;left:15%;top:9%;width:155px;height:155px;border-radius:50%;background:#eacfa1aa;box-shadow:0 0 80px 40px #e5cc9720}.stem{position:absolute;left:55%;bottom:22%;height:calc(80px + var(--grow)*200px);border-left:7px solid #7f9861;transform:rotate(8deg)}.leaf{position:absolute;background:#a5b17b;width:98px;height:40px;border-radius:0 100%;left:42%;bottom:32%;transform:rotate(30deg);opacity:.7}.leaf.b{left:57%;bottom:46%;transform:rotate(-20deg);background:#7b9877}.bloom{position:absolute;left:45%;bottom:calc(26% + var(--grow)*37%);font:170px Georgia;color:#c68f7b;transform:scale(calc(.45 + var(--grow)*.55));line-height:1}.ground{position:absolute;left:5%;bottom:10%;width:90%;height:70px;border-radius:50%;background:#a7b28a38}.spark{position:absolute;left:76%;top:18%;font-size:55px;color:#b49b65}#garden{padding:100px 8vw 140px;background:#e5e9d955;min-height:800px}h2{font-weight:400;font-size:58px;margin:35px 0 15px}.garden-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:40px;margin-top:65px}article{padding:35px 26px;border-top:1px solid #84957388;min-height:280px;position:relative;outline:none}article span{font:13px system-ui;color:#8a9575;letter-spacing:3px}h3{font-size:32px;font-weight:400}article p{font-size:18px}.leaflet{position:absolute;right:30px;bottom:0;font-size:75px;color:#8b9e70}#hover-card:hover,#hover-card:focus{background:#f7f2e2}#hover-card:hover .leaflet,#hover-card:focus .leaflet{color:#bf8e70;transform:rotate(-20deg) scale(1.25)}footer{padding:60px 8vw;font-size:20px}footer span{float:right;color:#8b977e}@media(max-width:800px){.hero{grid-template-columns:1fr;min-height:900px}.drawing{height:280px}.garden-grid{gap:10px}h2{font-size:42px}}
</style>
<script>
let planted=false;document.getElementById('button').addEventListener('click',()=>{planted=true;document.getElementById('button').firstChild.textContent='花已经开了 ';document.getElementById('status').textContent='谢谢你，这片花园多了一点颜色。';});
const random=seed=>{let s=seed>>>0;return ()=>{s=(Math.imul(s,1664525)+1013904223)>>>0;return s/4294967296;};};
window.webfilm={duration:12,render(t){const drawing=document.getElementById('drawing');drawing.style.setProperty('--breathe',Math.sin(t*1.5)*5);drawing.style.setProperty('--grow',planted?1:0);}};
</script>
"""


def _page(title: str, body: str, script: str = "") -> str:
    return ("<!doctype html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{title}</title><style>{_STYLE}</style></head><body>\n{body}\n"
            f"<script>{script}</script><script src=\"runtime.js\"></script></body></html>\n")


def create_demo(destination) -> dict:
    """Write six original code works; refuse all pre-existing nonempty targets."""
    root = Path(destination).expanduser().absolute()
    if root.is_symlink():
        raise ValueError("demo target cannot be a symbolic link")
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise FileExistsError("demo requires a new or empty isolated directory")
    root.mkdir(parents=True, exist_ok=True)
    runtime = Path(__file__).with_name("runtime.js")
    works = (
        ("animation", "纸上远行", 20, "generated"),
        ("interactive", "小小的交互花园", 12, "none"),
        ("card", "一步一段旅程", 8, "generated"),
        ("opener", "带着好奇心出发", 4, "generated"),
        ("outro", "把好奇心带回日常", 6, "generated"),
        ("cover", "纸上远行封面", 1, "none"),
    )
    for name, title, duration, audio in works:
        folder = root / name
        folder.mkdir()
        config = {"schema": 1, "title": title, "entry": "index.html", "duration": duration,
                  "seed": 829, "audio": audio}
        (folder / "work.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if name == "interactive":
            page = _page(title, _INTERACTIVE)
        else:
            interface = (f"window.webfilm={{duration:{duration},render(t){{paint(t,'{name}',{duration});}}"
                         + (f",audio(ctx){{return score(ctx,{duration});}}" if audio == "generated" else "") + "};")
            page = _page(title, '<canvas id="scene" aria-label="原创纸纹水彩小鸟旅程"></canvas>',
                         _PAINTER + (_AUDIO if audio == "generated" else "") + interface)
        (folder / "index.html").write_text(page, encoding="utf-8")
        shutil.copyfile(runtime, folder / "runtime.js")
    actions = {"schema": 1, "actions": [
        {"at": .5, "type": "move", "x": 340, "y": 400},
        {"at": 1, "type": "click", "selector": "#button"},
        {"at": 2, "type": "scroll", "y": 800, "duration": 1},
        {"at": 4, "type": "hover", "selector": "#hover-card"},
        {"at": 6, "type": "wait"},
    ]}
    (root / "interactive" / "actions.json").write_text(json.dumps(actions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "prompt.txt").write_text(PROMPT + "\n", encoding="utf-8")
    site = {"schema": 1, "title": "网页代码作品彩排", "prompt": PROMPT,
            "notice": "AI 补充的渲染验收样片。两位虚构彩排作者使用同一份作品，未进行实际模型比赛，也不是给参赛模型的模板。",
            "entries": [{"name": name, "versions": [{"name": "第一版", "work": "animation"},
                                                     {"name": "修改版", "work": "animation"}]}
                        for name in ("彩排 A", "彩排 B")]}
    (root / "site.json").write_text(json.dumps(site, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"schema": "webfilm.demo.v1", "destination": str(root.resolve()),
            "works": [name for name, _, _, _ in works], "site": str(root / "site.json"),
            "provenance": "AI supplemental capture fixture, not a contest template. Original Canvas2D / DOM and generated Web Audio; fictional entries."}
