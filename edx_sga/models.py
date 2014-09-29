import mongoengine

class Submission(models.Model):
	sha1 = mongoengine.StringField(max_length=160, min_length=None)
	document = mongoengine.FileField()
	
