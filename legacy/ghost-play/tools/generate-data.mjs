import { mkdir, writeFile } from 'node:fs/promises';
import { generateMatch, SCENARIOS } from '../lib/football.mjs';

const seed=Number(process.argv[2]??42);
if(!Number.isInteger(seed)||seed<0||seed>4294967295)throw new Error('Seed must be an integer between 0 and 4294967295');
const folder=new URL('../data/',import.meta.url);
await mkdir(folder,{recursive:true});
for(const scenario of SCENARIOS){const match=generateMatch(scenario.id,seed);await writeFile(new URL(`${scenario.id}-${seed}.json`,folder),JSON.stringify(match,null,2)+'\n');console.log(`Generated data/${scenario.id}-${seed}.json`);}
