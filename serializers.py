from rest_framework import serializers

# TODO: make a validation via serializers

class RequestSerializer(serializers.Serializer):
    hostname = serializers.CharField(max_length=256)
    vendor = serializers.CharField(max_length=256)
    command = serializers.CharField(max_length=256)
    result = serializers.CharField(max_length=256)
