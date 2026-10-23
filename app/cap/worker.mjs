// Cap 0.1.6: local bounded RPC worker, no HTTP listener or dashboard.
import readline from 'node:readline';
import {generateChallenge, validateChallenge} from './core/src/index.js';
const secret=process.env.GATEARR_CAP_SECRET;
if(!secret||secret.length<32)process.exit(78);
for await(const line of readline.createInterface({input:process.stdin,crlfDelay:Infinity})){
 try{const msg=JSON.parse(line);let nonce;
  const result=msg.action==='challenge'?await generateChallenge(secret,{scope:msg.scope,format:2,protocols:['hashwx','instrumentation'],hashwxDifficulty:500000,expiresMs:300000,instrumentation:{obfuscationLevel:1,blockAutomatedBrowsers:false}}):await validateChallenge(secret,msg.body,{scope:msg.scope,tokenTtlMs:300000,consumeNonce:async sig=>{nonce=sig;return true;}});
  process.stdout.write(JSON.stringify({...result,nonce})+'\n');
 }catch{process.stdout.write('{"success":false,"reason":"unavailable"}\n');}
}
