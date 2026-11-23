const {chromium}=require('playwright');const {spawn}=require('child_process');
(async()=>{
  const mode=process.argv[2]; const b=await chromium.launch(); const pg=await b.newPage({viewport:{width:1920,height:1080}});
  await pg.goto('file://'+__dirname+'/tour.html'); await pg.evaluate(()=>document.fonts.ready); await pg.waitForTimeout(800);
  if(mode==='preview'){ for(const t of process.argv.slice(3)){ await pg.evaluate(t=>seek(t),+t); await pg.screenshot({path:`p_${t}.jpg`,type:'jpeg',quality:80}); } await b.close(); return; }
  const fps=30,dur=45.5,N=Math.round(fps*dur);
  const ff=spawn('ffmpeg',['-y','-v','error','-f','image2pipe','-framerate',''+fps,'-c:v','mjpeg','-i','-','-c:v','libx264','-preset','slow','-crf','26','-pix_fmt','yuv420p','-movflags','+faststart','out.mp4'],{stdio:['pipe','inherit','inherit']});
  for(let i=0;i<N;i++){ await pg.evaluate(t=>seek(t),i/fps); const buf=await pg.screenshot({type:'jpeg',quality:92}); if(!ff.stdin.write(buf)) await new Promise(r=>ff.stdin.once('drain',r)); }
  ff.stdin.end(); await new Promise(r=>ff.on('close',r)); await b.close();
})();
