"""Canvas eligibility, deterministic replay, output completeness and lease cleanup."""
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from webfilm.webcodecs import canvas_session, capture_canvas, hardware_lease


FIXTURE = r"""
const fs=require('fs'); global.crypto=require('crypto').webcrypto; global.window=global;
global.innerWidth=2; global.innerHeight=2; global.devicePixelRatio=1;
const style={display:'block',visibility:'visible',opacity:'1',filter:'none',backdropFilter:'none',
 transform:'none',perspective:'none',clipPath:'none',maskImage:'none',mixBlendMode:'normal',boxShadow:'none',
 rotate:'none',scale:'none',translate:'none',clip:'auto',borderRadius:'0px',zoom:'1',overflowX:'visible',
 overflowY:'visible',contentVisibility:'visible',outlineStyle:'none',outlineWidth:'0px',
 objectFit:'fill',objectPosition:'50% 50%',backgroundColor:'rgba(0, 0, 0, 0)',backgroundImage:'none',backgroundClip:'border-box',colorScheme:'normal'};
for(const side of ['Top','Right','Bottom','Left']) {style['border'+side+'Width']='0px';style['padding'+side]='0px';}
const rect={left:0,top:0,right:2,bottom:2,width:2,height:2};
const make=(tag,parent=null)=>({tagName:tag,parentElement:parent,childNodes:[],getBoundingClientRect:()=>rect});
const html=make('HTML'),body=make('BODY',html),canvas=make('CANVAS',body);canvas.width=2;canvas.height=2;
const context={getContextAttributes:()=>({colorSpace:'srgb',alpha:process.argv[2]==='composite'}),getImageData:()=>{
 const data=new Uint8ClampedArray(16);for(let i=0;i<16;i+=4){data[i]=Math.round(__WEBFILM_TIME__*10);data[i+3]=255;}
 if(['alpha','composite'].includes(process.argv[2]))data[3]=254;return {data};}};
canvas.getContext=()=>{throw Error('Unexpected getContext probe');};global.Node={TEXT_NODE:3};
global.__WEBFILM_CANVAS_CONTEXTS__=new WeakMap([[canvas,{type:process.argv[2]==='webgl'?'webgl2':'2d',context}]]);
global.getComputedStyle=(node,pseudo)=>pseudo?{content:'none',display:'none'}:{...style,...node.style};
global.document={querySelectorAll:s=>s==='canvas'?[canvas]:[html,body,canvas],querySelector:()=>null,
 getAnimations:()=>[],body,documentElement:{style:{}}};
let calls=[],encoded=[],closed=0,written=[],created=0,keyframes=[];
global.webfilm={render:async t=>calls.push(t)};
global.sink=async m=>{if(process.argv[2]==='write-error'&&m.kind==='chunk')throw Error('binding write failed');written.push(m);};
global.OffscreenCanvas=class{constructor(){this.context={fillRect(){},drawImage(){this.data=context.getImageData().data;
 for(let i=0;i<16;i+=4){const alpha=this.data[i+3]/255;for(let j=0;j<3;j++)this.data[i+j]=this.data[i+j]*alpha+255*(1-alpha);this.data[i+3]=255;}}};}
 getContext(){return this.context;}};
global.VideoFrame=class{constructor(c,options){Object.assign(this,options);this.data=c===canvas?context.getImageData().data:c.context.data;}
 allocationSize(){return 16;}async copyTo(bytes){bytes.set(this.data);return [{offset:0,stride:8}];}close(){closed++;}};
global.VideoEncoder=class {
 static async isConfigSupported(config){return {supported:process.argv[2]!=='unsupported',config};}
 constructor(callbacks){created++;this.callbacks=callbacks;this.state='configured';this.encodeQueueSize=0;}
 configure(config){if('framerate' in config)throw Error('Unexpected framerate hint');}
 encode(frame,flags){if(flags.keyFrame)keyframes.push(frame.timestamp);encoded.push(frame.timestamp);const options=this.callbacks;
  Promise.resolve().then(()=>options.output({timestamp:frame.timestamp+(process.argv[2]==='timestamp-error'?1:0),
   byteLength:1,copyTo:bytes=>bytes[0]=1,type:'key',duration:frame.duration}));}
 async flush(){await Promise.resolve();}close(){this.state='closed';}addEventListener(){}
};
const run=Function('return ('+fs.readFileSync(process.argv[1],'utf8')+')')();
(async()=>{
 if(process.argv[2]==='padding')canvas.style={paddingTop:'1px'};
 if(process.argv[2]==='transform')html.style={rotate:'180deg'};
 if(['background','dark','clip'].includes(process.argv[2])){body.style={backgroundImage:process.argv[2]==='background'?'linear-gradient(red,blue)':'none',backgroundClip:process.argv[2]==='clip'?'content-box':'border-box'};html.style={colorScheme:process.argv[2]==='dark'?'dark':'normal'};context.getContextAttributes=()=>({colorSpace:'srgb',alpha:true});}
 const args={fps:60,start:90,end:102,binding:'sink',cached:null,verifyFrames:['cache','changed','full'].includes(process.argv[2]),keepEncoder:process.argv[2]==='session'};
 const first=await run(args);let second=null;
 if(process.argv[2]==='session'){second=await run({...args,start:102,end:114});window.__WEBFILM_ENCODER_SESSION__.encoder.close();delete window.__WEBFILM_ENCODER_SESSION__;}
 if(['cache','changed','sample-cache'].includes(process.argv[2])){
  encoded=[];calls=[];const cached=[...first.frames];if(process.argv[2]==='changed')cached[2]='old';
  second=await run({...args,cached});
 }
 console.log(JSON.stringify({first,second,encoded,calls,closed,written,created,keyframes}));
})().catch(error=>{console.log(JSON.stringify({error:String(error)}));});
"""


class WebCodecsTests(unittest.TestCase):
    def js(self, mode='normal'):
        if not shutil.which('node'):
            self.skipTest('Node is required for the isolated WebCodecs callback fixture')
        result = subprocess.run(['node', '-e', FIXTURE, str(Path(__file__).parents[1]/'webfilm/webcodecs.js'), mode],
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_exact_input_clock_output_count_and_closed_frames(self):
        result = self.js()
        self.assertNotIn('error', result)
        self.assertEqual(result['calls'], [i/60 for i in range(90, 102)])
        self.assertEqual(result['encoded'], [round(i*1e6/60) for i in range(12)])
        self.assertEqual([t for m in result['written'] if m['kind'] == 'chunk' for t in m['timestamps']], result['encoded'])
        self.assertEqual(result['closed'], 12)
        self.assertEqual(result['first']['frame_indices'], [90, 96, 101])
        self.assertEqual(len(result['first']['frames']), 3)
        self.assertTrue(all(len(h) == 64 for h in result['first']['frames']))
        self.assertTrue(result['first']['evidence']['sampled'])
        self.assertEqual(len(self.js('full')['first']['frames']), 12)

    def test_webgl_and_alpha_composition_use_sampled_video_frame_pixels(self):
        self.assertEqual(self.js('webgl')['first']['evidence']['context_types'], ['webgl2'])
        composited = self.js('composite')['first']
        self.assertTrue(composited['evidence']['alpha_composed'])
        self.assertEqual(len(composited['frames']), 3)
        self.assertEqual(composited['frames'][0], hashlib.sha256(bytes([16, 1, 1]+[15, 0, 0]*3)).hexdigest())

    def test_shared_encoder_keeps_coded_clock_and_rebases_segment_bindings(self):
        result = self.js('session')
        self.assertEqual(result['created'], 1); self.assertEqual(result['keyframes'], [0, 200000])
        self.assertEqual(result['encoded'], [round(i*1e6/60) for i in range(24)])
        self.assertEqual(result['second']['evidence']['encoder_origin_frame'], 90)
        self.assertEqual([t for m in result['written'] if m['kind'] == 'chunk' for t in m['timestamps']], [round(i*1e6/60) for i in range(12)]*2)

    def test_cache_reuses_only_matching_pixels_and_replays_changed_prefix(self):
        same, changed = self.js('cache'), self.js('changed')
        self.assertTrue(same['second']['reused'])
        self.assertEqual(same['encoded'], [])
        self.assertFalse(changed['second']['reused'])
        self.assertEqual(changed['second']['frames'], changed['first']['frames'])
        self.assertEqual(len(changed['encoded']), 12)
        self.assertEqual(changed['calls'][:5], [1.5, 91/60, 92/60, 1.5, 91/60])
        sampled = self.js('sample-cache')
        self.assertFalse(sampled['second']['reused']); self.assertEqual(len(sampled['encoded']), 12)

    def test_css_transparency_and_async_output_failure_are_not_accepted(self):
        for mode in ('alpha', 'padding', 'transform', 'unsupported', 'background', 'dark', 'clip'):
            with self.subTest(mode=mode):
                self.assertIn('unsupported', self.js(mode)['first'])
        for mode in ('write-error', 'timestamp-error'):
            with self.subTest(mode=mode):
                self.assertIn('error', self.js(mode))

    def test_python_capture_rejects_missing_outputs_and_copies_valid_cache(self):
        class Page:
            def expose_function(self, name, receive):
                self.receive = receive
        page, runtime = Page(), {'blocked': [], 'failures': []}
        with tempfile.TemporaryDirectory() as folder, patch('webfilm.webcodecs.assert_runtime'):
            output = Path(folder)/'out.h264'
            result = {'frames': ['a'], 'reused': False, 'evidence': {}}
            with patch('webfilm.webcodecs.evaluate', side_effect=[result, None]), self.assertRaises(ValueError):
                capture_canvas(page, runtime, output, 60, 0, 1)
            output.unlink()
            cached = Path(folder)/'old.h264'; cached.write_bytes(b'encoded')
            result.update(reused=True)
            with patch('webfilm.webcodecs.evaluate', side_effect=[result, None]):
                saved = capture_canvas(page, runtime, output, 60, 0, 1,
                                       cached={'frames': ['a'], 'video': cached, 'evidence': {'source': 'old'}}, verify_frames=True)
            self.assertEqual(output.read_bytes(), b'encoded')
            self.assertEqual(saved['timing']['encoded_frames'], 0)

    def test_gpu_lease_always_releases_on_capture_failure(self):
        calls = []
        def request(lease, action, **payload):
            calls.append((action, payload)); return {'ok': True, 'token': 'fixture-token'}
        with patch.dict('os.environ', WEBFILM_GPU_BROKER='http://127.0.0.1:1'), \
                patch('webfilm.webcodecs.HardwareLease.request', request), patch('webfilm.webcodecs.evaluate') as finish:
            with self.assertRaisesRegex(RuntimeError, 'capture failed'):
                with hardware_lease(), canvas_session(None):
                    raise RuntimeError('capture failed')
        self.assertEqual([c[0] for c in calls], ['acquire', 'release'])
        self.assertEqual(calls[0][1]['owner'], 'webfilm')
        self.assertEqual(calls[0][1]['ttl_seconds'], 300)
        finish.assert_called_once()
        self.assertIsNone(finish.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
