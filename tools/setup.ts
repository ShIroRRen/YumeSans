import { existsSync } from 'node:fs'
import { join } from 'node:path'

import { ensureCnFontSplitNative } from './cnfs'

const ROOT = join(import.meta.dir, '..')
const VENV = join(ROOT, '.venv')
const isWin = process.platform === 'win32'
const venvPython = join(VENV, isWin ? 'Scripts/python.exe' : 'bin/python')
const venvBin = join(VENV, isWin ? 'Scripts' : 'bin')

async function cmd(cmd: string[], cwd = ROOT): Promise<number> {
	return await Bun.spawn(cmd, { cwd, stdout: 'inherit', stderr: 'inherit' }).exited
}

function which(bin: string): boolean {
	const PATH = (process.env.PATH ?? '').split(isWin ? ';' : ':')
	const exts = isWin ? ['.exe', ''] : ['']
	return PATH.some(dir => (!dir ? false : exts.some(ext => existsSync(join(dir, bin + ext)))))
}

if (!which('uv')) {
	console.error('✗ uv not found')
	process.exit(1)
} else console.log('✓ uv')

for (const bin of ['hb-subset', 'hb-shape']) console.log(which(bin) ? `✓ ${bin}` : `✗ ${bin} not found`)
const pyOk = (await cmd(['python', '-c', 'import fontTools, brotli'], ROOT)) === 0
console.log(pyOk ? '✓ fontTools + brotli (python)' : '✗ fontTools/brotli not found (python)')

if (!existsSync(venvPython)) {
	const code = await cmd(['uv', 'venv', '--python', '3.14', VENV])
	if (code !== 0) process.exit(code)
}

const has = (name: string) =>
	existsSync(join(venvBin, isWin ? `${name}.exe` : name)) || existsSync(join(VENV, 'Lib/site-packages', name))

if (!has('nanoemoji') || !has('ninja')) {
	const code = await cmd(['uv', 'pip', 'install', '--python', venvPython, 'nanoemoji', 'ninja'])
	if (code !== 0) process.exit(code)
}
console.log('✓ nanoemoji + ninja (venv)')

await ensureCnFontSplitNative()
console.log('✓ cn-font-split native')