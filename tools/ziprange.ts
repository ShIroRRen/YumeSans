import { inflateRawSync } from 'node:zlib'

const EOCD_SIG = 0x06054b50
const CD_SIG = 0x02014b50
const LFH_SIG = 0x04034b50

export type ZipEntry = {
	name: string
	compressedSize: number
	uncompressedSize: number
	method: number
	localHeaderOffset: number
}

async function contentLength(url: string): Promise<number> {
	const res = await fetch(url, { method: 'HEAD', redirect: 'follow' })
	if (!res.ok) throw new Error(`HEAD ${url} -> ${res.status}`)
	const len = Number(res.headers.get('content-length'))
	if (!len) throw new Error(`no Content-Length for ${url}`)
	return len
}

async function range(url: string, start: number, end: number): Promise<Buffer> {
	const res = await fetch(url, {
		headers: { Range: `bytes=${start}-${end}` },
		redirect: 'follow'
	})
	if (res.status !== 206 && res.status !== 200) throw new Error(`range ${start}-${end} -> HTTP ${res.status}`)
	return Buffer.from(await res.arrayBuffer())
}

export async function listZip(url: string): Promise<ZipEntry[]> {
	const size = await contentLength(url)
	const tailLen = Math.min(size, 66 * 1024)
	const tail = await range(url, size - tailLen, size - 1)

	let eocd = -1
	for (let i = tail.length - 22; i >= 0; i--)
		if (tail.readUInt32LE(i) === EOCD_SIG) {
			eocd = i
			break
		}
	if (eocd < 0) throw new Error(`EOCD not found in ${url}`)

	const cdEntryCount = tail.readUInt16LE(eocd + 10)
	const cdSize = tail.readUInt32LE(eocd + 12)
	const cdOffset = tail.readUInt32LE(eocd + 16)

	let cd =
		cdOffset >= size - tailLen
			? tail.subarray(cdOffset - (size - tailLen), cdOffset - (size - tailLen) + cdSize)
			: await range(url, cdOffset, cdOffset + cdSize - 1)

	const entries: ZipEntry[] = []
	let p = 0
	for (let i = 0; i < cdEntryCount; i++) {
		if (cd.readUInt32LE(p) !== CD_SIG) throw new Error(`bad CD signature at ${p}`)
		const method = cd.readUInt16LE(p + 10)
		const compressedSize = cd.readUInt32LE(p + 20)
		const uncompressedSize = cd.readUInt32LE(p + 24)
		const nameLen = cd.readUInt16LE(p + 28)
		const extraLen = cd.readUInt16LE(p + 30)
		const commentLen = cd.readUInt16LE(p + 32)
		const localHeaderOffset = cd.readUInt32LE(p + 42)
		const name = cd.subarray(p + 46, p + 46 + nameLen).toString('utf8')
		entries.push({ name, compressedSize, uncompressedSize, method, localHeaderOffset })
		p += 46 + nameLen + extraLen + commentLen
	}
	return entries
}

export async function readZipEntry(url: string, entry: ZipEntry): Promise<Buffer> {
	const lfh = await range(url, entry.localHeaderOffset, entry.localHeaderOffset + 29)
	if (lfh.readUInt32LE(0) !== LFH_SIG) throw new Error(`bad local header for ${entry.name}`)
	const nameLen = lfh.readUInt16LE(26)
	const extraLen = lfh.readUInt16LE(28)
	const dataStart = entry.localHeaderOffset + 30 + nameLen + extraLen
	const dataEnd = dataStart + entry.compressedSize - 1
	const raw = await range(url, dataStart, dataEnd)
	if (entry.method === 0) return raw
	if (entry.method === 8) return inflateRawSync(raw)
	throw new Error(`unsupported compression method ${entry.method} for ${entry.name}`)
}

export async function fetchFromZip(url: string, match: RegExp): Promise<Buffer> {
	const entries = await listZip(url)
	const hit = entries.find(e => match.test(e.name))
	if (!hit) throw new Error(`no entry matching ${match} in ${url}`)
	return readZipEntry(url, hit)
}