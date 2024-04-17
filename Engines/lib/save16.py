import hashlib
import random
import struct

masterKeyPes16 = [
    0x4D, 0x55, 0x94, 0x66, 0xD9, 0x62, 0x5C, 0xEC,
    0xC1, 0x7C, 0x48, 0x36, 0x77, 0x31, 0x50, 0xE1,
    0x87, 0x1C, 0xB5, 0x6B, 0x41, 0xD4, 0x92, 0x4F,
    0x4A, 0x8C, 0x71, 0x27, 0x0A, 0x0D, 0x50, 0x63,
    0x94, 0x2B, 0x58, 0x5E, 0x99, 0x0B, 0x8B, 0x97,
    0x96, 0x66, 0xC0, 0x00, 0xB7, 0x1D, 0x72, 0x75,
    0xD6, 0xE8, 0x5B, 0x0E, 0xAF, 0xF1, 0x72, 0xD1,
    0xB1, 0xE3, 0x3C, 0x75, 0xDE, 0x9C, 0x13, 0x09,
]
masterKey = masterKeyPes16
effectiveMasterKey = bytes([
	masterKey[(i & ~7) + 7 - (i & 7)] for i in range(len(masterKey))
])

class ParseError(Exception):
	pass

class mersenne_rng(object):
	def __init__(self, seed = 5489):
		self.state = [0]*624
		self.f = 1812433253
		self.m = 397
		self.u = 11
		self.s = 7
		self.b = 0x9D2C5680
		self.t = 15
		self.c = 0xEFC60000
		self.l = 18
		self.index = 624
		self.lower_mask = (1<<31)-1
		self.upper_mask = 1<<31
		
		if type(seed) == int:
			self.seed(c_seed)
		elif type(seed) == list:
			self.seed_list(seed)
		else:
			raise ValueError("unexpected")

	def seed(self, seed):
		# update state
		self.state[0] = seed
		for i in range(1,624):
			self.state[i] = self.int_32(self.f*(self.state[i-1]^(self.state[i-1]>>30)) + i)

	def seed_list(self, data):
		self.seed(19650218)
		i = 1
		j = 0
		for k in range(max(len(self.state), len(data))):
			temp = ((self.state[i - 1] ^ (self.state[i - 1] >> 30)) * 1664525) & 0xffffffff
			self.state[i] = ((self.state[i] ^ temp) + data[j] + j) & 0xffffffff
			i += 1
			if i >= len(self.state):
				self.state[0] = self.state[len(self.state) - 1]
				i = 1
			j = (j + 1) % len(data)
		for k in range(len(self.state) - 1):
			temp = ((self.state[i - 1] ^ (self.state[i - 1] >> 30)) * 1566083941) & 0xffffffff
			self.state[i] = ((self.state[i] ^ temp) + 0x100000000 - i) & 0xffffffff
			i += 1
			if i >= len(self.state):
				self.state[0] = self.state[len(self.state) - 1]
				i = 1
		self.state[0] = 0x80000000
	
	def twist(self):
		for i in range(624):
			temp = self.int_32((self.state[i]&self.upper_mask)+(self.state[(i+1)%624]&self.lower_mask))
			temp_shift = temp>>1
			if temp%2 != 0:
				temp_shift = temp_shift^0x9908b0df
			self.state[i] = self.state[(i+self.m)%624]^temp_shift
		self.index = 0
	
	def get_random_number(self):
		if self.index >= 624:
			self.twist()
		y = self.state[self.index]
		y = y^(y>>self.u)
		y = y^((y<<self.s)&self.b)
		y = y^((y<<self.t)&self.c)
		y = y^(y>>self.l)
		self.index+=1
		return self.int_32(y)
	
	def int_32(self, number):
		return int(0xFFFFFFFF & number)

class SaveFile:
	def __init__(self):
		self.identifier = None
		self.description = None
		self.logo = None
		self.payload = None
		self.serial = None
	
	@staticmethod
	def cryptStream(key, length):
		foo = struct.unpack('< 16I', key)
		twister = mersenne_rng(list(foo))
		output = bytearray(length)
		
		c0 = twister.get_random_number()
		c1 = twister.get_random_number()
		c2 = twister.get_random_number()
		c3 = twister.get_random_number()
		
		def rol(value, bits):
			return ((value << bits) & 0xffffffff) | (value >> (32 - bits))
		def ror(value, bits):
			return rol(value, 32 - bits)
		index = 0
		output = bytearray((length + 3) // 4 * 4)
		for i in range((length + 3) // 4):
			c4 = twister.get_random_number()
			v = c4 ^ c3 ^ c2 ^ c1 ^ c0
			
			c0 = ror(c1, 15)
			c1 = rol(c2, 11)
			c2 = rol(c3, 7)
			c3 = ror(c4, 13)
			
			struct.pack_into('<I', output, i * 4, v)
		return output[0:length]
	
	@staticmethod
	def xor(data, key):
		return bytearray([data[i] ^ key[i % len(key)] for i in range(len(data))])
	
	@staticmethod
	def cryptData(key, data):
		return SaveFile.xor(data, SaveFile.cryptStream(key, len(data)))
	
	@staticmethod
	def decryptSalt(salt):
		headerKey = SaveFile.xor(effectiveMasterKey, salt[256:320])
		decryptedSalt = SaveFile.cryptData(headerKey, salt[0:256]) + salt[256:320]
		return SaveFile.xor(SaveFile.xor(SaveFile.xor(SaveFile.xor(
			decryptedSalt[0:64],
			decryptedSalt[64:128]),
			decryptedSalt[128:192]),
			decryptedSalt[192:256]),
			decryptedSalt[256:320])
	
	def load(self, filename):
		data = open(filename, 'rb').read()
		
		salt = data[0:320]
		key = SaveFile.decryptSalt(salt)
		offset = 320
		
		header = SaveFile.cryptData(SaveFile.xor(key, struct.pack('<Q', 176)), data[offset : offset + 176])
		offset += 176
		
		if header[0:64] != effectiveMasterKey:
			raise ParseError()
		
		(payloadSize, logoSize, descriptionSize, serialSize) = struct.unpack('< 4I', header[64:80])
		self.identifier = header[80:]
		
		self.description = SaveFile.cryptData(SaveFile.xor(key, struct.pack('<Q', 0)), data[offset : offset + descriptionSize])
		offset += descriptionSize
		
		self.logo = SaveFile.cryptData(SaveFile.xor(key, struct.pack('<Q', 1)), data[offset : offset + logoSize])
		offset += logoSize
		
		self.payload = SaveFile.cryptData(SaveFile.xor(key, struct.pack('<Q', 2)), data[offset : offset + payloadSize])
		offset += payloadSize
		
		self.serial = SaveFile.cryptData(SaveFile.xor(key, struct.pack('<Q', 3)), data[offset : offset + serialSize * 2])
		offset += serialSize * 2
	
	def save(self, filename):
		salt = bytes([random.randint(0, 255) for i in range(320)])
		key = SaveFile.decryptSalt(salt)
		
		header = effectiveMasterKey + struct.pack('< 4I',
			len(self.payload),
			len(self.logo),
			len(self.description),
			len(self.serial) // 2
		) + self.identifier
		
		output = (
			  salt
			+ SaveFile.cryptData(SaveFile.xor(key, struct.pack('<Q', 176)), header)
			+ SaveFile.cryptData(SaveFile.xor(key, struct.pack('<Q', 0)), self.description)
			+ SaveFile.cryptData(SaveFile.xor(key, struct.pack('<Q', 1)), self.logo)
			+ SaveFile.cryptData(SaveFile.xor(key, struct.pack('<Q', 2)), self.payload)
			+ SaveFile.cryptData(SaveFile.xor(key, struct.pack('<Q', 3)), self.serial)
		)
		
		with open(filename, 'wb') as f:
			f.write(output)

def loadPlayers(save):
	(playerCount, ) = struct.unpack('<H', save[0x36:0x38])
	
	playerIDs = set()
	playerData = {}
	for i in range(playerCount):
		data = save[0x4c + 112 * i : 0x4c + 112 * (i + 1)]
		(playerID, ) = struct.unpack('<I', data[0:4])
		playerData[playerID] = data
		playerIDs.add(playerID)
	
	playerAestheticsData = {}
	for i in range(playerCount):
		data = save[0x2ab9cc + 72 * i : 0x2ab9cc + 72 * (i + 1)]
		(playerID, ) = struct.unpack('<I', data[0:4])
		playerAestheticsData[playerID] = data
		playerIDs.add(playerID)
	
	return { playerID: (playerData.get(playerID), playerAestheticsData.get(playerID)) for playerID in playerIDs }

def savePlayers(save, players):
	(playerCount, ) = struct.unpack('<H', save[0x36:0x38])
	
	for i in range(playerCount):
		data = save[0x4c + 112 * i : 0x4c + 112 * (i + 1)]
		(playerID, ) = struct.unpack('<I', data[0:4])
		if playerID in players:
			(playerData, playerAestheticsData) = players.get(playerID)
			if playerData is not None:
				assert len(playerData) == 112, "Invalid player data block"
				save[0x4c + 112 * i : 0x4c + 112 * (i + 1)] = playerData
	
	for i in range(playerCount):
		data = save[0x2ab9cc + 72 * i : 0x2ab9cc + 72 * (i + 1)]
		(playerID, ) = struct.unpack('<I', data[0:4])
		if playerID in players:
			(playerData, playerAestheticsData) = players.get(playerID)
			if playerAestheticsData is not None:
				assert len(playerAestheticsData) == 72, "Invalid player aesthetics data block"
				save[0x2ab9cc + 72 * i : 0x2ab9cc + 72 * (i + 1)] = playerAestheticsData