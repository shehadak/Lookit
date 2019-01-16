import xml.etree.ElementTree as ET
import csv
tree=ET.parse('trial_file.vcx')

class Response():
	def __init__(self, ID, time, trial, trial_status, Type):
		self.ID = ID # Response ID, starts from 1. (int)
		self.time=time # Time of response in frames. (int)
		self.trial=trial # Trial Number. (int)
		self.trial_status=trial_status # Trial Status. (boolean)
		self.Type=Type # Trial Type: right, left, away, or off. (str)
	def __str__(self):
		return('Response %i at time %i at trial %i, which is %s is at %s' %(self.ID,self.time,self.trial,"active" if self.trial_status else "inactive",self.Type))

	def __eq__(self,other):
		return(self.ID == other.ID and self.time==other.time and self.trial==other.trial and self.trial_status == other.trial_status and self.Type==other.Type)
def XMLDict_to_Pythondict(XML_Dict):
	""" Takes an XML dictionary (an XML object with the tag "dict")
		Returns a python dictionary mapping each key to its value in a python-readable form
		"""
	def array_to_list(array_item):
		l=[]
		for item in array_item:
			if item.tag=='dict':
				l.append(XMLDict_to_Pythondict(item))
			elif item.tag=='true' or item.tag=='false':
				l.append(item.tag)
			else:
				l.append(item.text)
		return(l)
	keys=[]
	values=[]
	for item in XML_Dict:
		if item.tag=='key':
			keys.append(item.text)
		elif item.tag=='dict':
			values.append(XMLDict_to_Pythondict(item))
		elif item.tag=='true' or item.tag=='false':
			values.append(item.tag)
		elif item.tag=='array':
			values.append(array_to_list(item))
		else:
			values.append(item.text)
	if len(keys)!=len(values):
		raise ValueError("Lengths are not equal")
	return({keys[i]:values[i] for i in range(len(keys))})

def extract_responses(tree):
	""" Takes a parsed XML (or vcx) file and extracts the important data
		Inputs: XML tree
		Returns: a dictionary on the form:
			{'Subject_info':dict mapping each attribute to its value, 'Responses': list of Response objects}
		"""
	def calculate_time(time_dict):
		Hours=int(time_dict['Hour'])
		Minutes=int(time_dict['Minute'])+60*Hours
		Seconds=int(time_dict['Second'])+60*Minutes
		Frames=int(time_dict['Frame'])+30*Seconds
		return(Frames)

	main_dict=XMLDict_to_Pythondict(tree.getroot().find('dict'))
	Subject_data=main_dict['Subject']
	Responses=Subject_data['Responses']
	del Subject_data['Responses']
	organized_responses=[]
	for resp in Responses:
		trial_stat=True if Responses[resp]['Trial Status']=='true' else False
		curr_Resp=Response(int(resp.split(" ")[1]),calculate_time(Responses[resp]['Timecode']), int(Responses[resp]['Trial']), trial_stat, Responses[resp]['Type'])
		organized_responses.append(curr_Resp)
	return({'Subject_info':Subject_data, 'Responses':sorted(organized_responses, key=lambda x: int(x.time))})

def get_trials(Data, unused_trials=False):
	""" Takes a list of Respone objects and a boolean to indicate whether to include non-coded trials or not.
		Returns a dictionary mapping each trial number to a list fo its responses.
		"""
	def get_unused_trials(Data):
		prescreened_out_dict=Data['Subject_info']['Pre-Screen Information']['Pre-Screen Array 0']
		prescreened_out_list=[]
		for entry in prescreened_out_dict:
			prescreened_out_list.append(int(prescreened_out_dict[entry]['Trial']))
		return([int(t) for t in Data['Subject_info']['Unused Trials']]+prescreened_out_list)
	total_trials={}
	Responses=Data['Responses']
	for res in Responses:
		if res.trial_status:
			if res.trial in total_trials:
				total_trials[res.trial].append(res)
			else:
				total_trials[res.trial]=[res]
	if unused_trials:
		for t in get_unused_trials(Data):
			total_trials[t]=[]
	sorted_dict={}
	for k in sorted(total_trials.keys()):
		sorted_dict[k]=total_trials[k]
	return(sorted_dict)

def Response_duration(Responses, Response):
	""" Takes a list of Response objects and a specific Response object.
		Returns the duration of the specific Response object (i.e. the time difference between the response and the next response/next off).
		Raises an error if the response is not in the responses list, if the response type is "off", or if the trial_status of the response is Fasle.
		"""
	if Response not in Responses:
		raise ValueError("Response not in responses!")
	if Response.Type=="off":
		raise ValueError('Responses of type "off" do not have a duration.')
	if Response.trial_status==False:
		raise ValueError('Responses with inactive trial do not have a duration.')
	next_resp=Responses[Responses.index(Response)+1]
	return(abs(next_resp.time-Response.time))

def get_total_time(Responses, types=[], trials=None, frames=False):
	""" Takes a list of Response objects, a list of response types (e.g. ['left','right', 'away']), and a list of trial numbers.
		If given a list of trials, returns the amount of time of all the responses of the types specified in the trials specified.
		If not given a list of trials, returns the total amount of time of all the responses of the types specified in all trials.
		If Frames is True, returns total time in 30*seconds. Otherwise returns in seconds.
		"""
	if "off" in types:
		raise ValueError("Responses of type 'off' do not have a duration.")
	if trials==None:
		val=sum([Response_duration(Responses, Resp) for Resp in Responses if Resp.Type in types and Resp.trial_status])
		return val if frames else round(val/30, 2)
	elif type(trials)==list:
		val=sum([Response_duration(Responses, Resp) for Resp in Responses if Resp.Type in types and Resp.trial in trials and Resp.trial_status])
		return val if frames else round(val/30,2)
	else:
		raise ValueError("Trials must be entered as a list, even if only one trial")

Data=extract_responses(tree)
Responses=Data['Responses']
# print(Data)
# for i in Responses:
# 	print(i)
Datav=get_trials(Data, True)
for i in range(len(Datav.keys())):
	print('Trial %i has the following responses:' %(list(Datav.keys())[i]))
	for res in list(Datav.values())[i]:
		print(res)

# print(get_total_time(Data['Responses'], ['left'], frames=False, trials=[9]))
# with open('tri.tsv', 'w') as tsv_file:
#     tsv_writer = csv.writer(tsv_file, delimiter='\t')
#     tsv_writer.writerow(['Trial Number', 'Right', 'Left', 'Away']) # First Row
#     for trial in get_trials(Data,True):
#     	tsv_writer.writerow([trial,
#     		str(get_total_time(Responses, ['right'],[trial])),
#     		str(get_total_time(Responses, ['left'],[trial])),
#     		str(get_total_time(Responses, ['away'],[trial]))
			# ])




