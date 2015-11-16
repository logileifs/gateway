import threading
import xmltodict
import unittest
import requests
import redis
import Queue
import json

payment_url = 'http://localhost:5000/viscus/cr/v1/payment'

OK = 200
NOT_ALLOWED = 405

app_xml = {'Content-Type': 'application/xml'}
text_xml = {'Content-Type': 'text/xml'}
app_json = {'Content-Type': 'application/json'}


red = redis.StrictRedis(host='localhost', port=6379, db=0)
ps = red.pubsub(ignore_subscribe_messages=True)
ps.subscribe('requests')

# Create a thread to run tasks in background
bg_thread = threading.Thread()
# Create a queue to store results from background thread
msg_store = Queue.Queue()


def get_msg():
	"""
	Pop message from message queue and return its payload
	"""
	msg = red.blpop('incoming', timeout=0)
	payload = msg[1]
	return json.loads(payload)


def post_xml_payment():
	global msg_store
	xml = get_xml_payment('tsys')
	http_rsp = requests.post(payment_url, data=xml, headers=app_xml)
	msg_store.put(http_rsp)


def post_json_payment():
	global msg_store
	json = get_json_payment('tsys')
	http_rsp = requests.post(payment_url, data=json, headers=app_json)
	msg_store.put(http_rsp)


def run_in_background(method):
	global bg_thread
	# Initialize thread with a method and run it in background
	bg_thread = threading.Thread(target=method, args=())
	bg_thread.start()


def get_result():
	"""
	Wait for background thread to finish, get its result from queue and return it
	"""
	global bg_thread
	global msg_store
	bg_thread.join()
	return msg_store.get()


class PaymentTests(unittest.TestCase):

	"""docstring"""

	def setUp(self):
		"""
		Initialization to be run before each test
		"""
		# Make sure the db is clean before each test
		red.flushdb()

	def tearDown(self):
		"""
		Cleanup to be run after each test
		"""
		pass

	@classmethod
	def setUpClass(cls):
		pass

	@classmethod
	def tearDownClass(cls):
		# Make sure db has been flushed after tests have finished
		red.flushdb()

	@unittest.skip("")
	def test_get(self):
		resp = requests.get(payment_url)
		assert resp.status_code == requests.codes.not_allowed
		assert resp.text == 'Method not allowed'


	#@unittest.skip("")
	def test_01_xml_payment_tsys(self):
		# Run the http post request in background and add the result to queue
		run_in_background(post_xml_payment)

		# Get the message from the rest interface incoming message queue
		msg = get_msg()

		# Assert that request was added to message queue
		assert msg is not None
		print(msg)

		guid = str(msg['payment']['guid'])

		# Create a core response
		core_rsp = create_core_rsp(guid)
		print('setting ' + guid + ' to queue')

		# Put the response on the outgoing queue
		red.set(guid, core_rsp)

		# Get the result from the queue
		http_rsp = get_result()
		print(http_rsp.text)
		assert http_rsp.status_code == requests.codes.ok

	#@unittest.skip("")
	def test_02_json_payment_tsys(self):
		run_in_background(post_json_payment)

		msg = get_msg()

		assert msg is not None
		print(msg)

		guid = str(msg['payment']['guid'])

		core_rsp = create_core_rsp(guid)

		red.set(guid, core_rsp)

		http_rsp = get_result()

		assert http_rsp is not None


def create_core_rsp(guid):
	core_rsp = \
		{
			'payment':
			{
				'paynentGuid': guid,
				'amount': '100.00',
				'currency': 'GBP',
				'cardTypeName': 'MasterCard',
				'maskedCardNumber': '************9004',
				'expiryDateMMYY': '0308',
				'customerReference': '00000040',
				'acquirerTid': '90008910',
				'approvalCode': '013795',
				'issuerResponseText': 'TPOS 0000',
				'batchNumber': '1215',
				'transNumber': '19711',
				'serverDateTime': '20130618154721688',
				'terminalDateTime': '20130618154657000',
				'agreementNumber': '6819106',
				'cardAcceptorName': 'DEV_PED08',
				'cardAcceptorAddress': 'DEV_PED08',
				'nonce': '7604056809'
			}
		}
	return json.dumps(core_rsp)


def get_xml_payment(route='tsys'):
	json_payment = json.loads(get_json_payment(route))
	xml_payment = xmltodict.unparse(json_payment, full_document=False)
	return xml_payment


def get_json_payment(route='tsys'):
	payment_json = \
		{
			"payment":
			{
				'cardAcceptorId': 'TestHekla5',
				'paymentScenario': 'CHIP',
				'softwareVersion': '1.3.1.15',
				'configVersion': '12',
				'terminalDateTime': '20130614172956000',
				'nonce': '7604056809',
				'authorizationGuid': '86ee88f8-3245-4fa6-a7fb-354ef1813854',
				'currency': 'GBP',
				'amount': '10.00',
				'customerReference': '00000001',
				'emvData': '4f07a00000000430605712679999',
				'f22': '51010151114C',
				'serialNumber': '311001304',
				'terminalUserId': 'OP1',
				'deviceType': 'MPED400',
				'terminalOsVersion': '1.08.00',
				'transactionCounter': '3',
				'accountType': '30',
				'route': route
			}
		}
	return json.dumps(payment_json)


if __name__ == '__main__':
	unittest.main()
