from rest_framework.decorators import api_view, renderer_classes, permission_classes
from rest_framework.response import Response
from rest_framework import permissions,authentication
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from collector import collector
import logging.config
import json

parser = collector.init_parser()
# Init logginig config
logger = logging.getLogger('collector')


@api_view(['GET', 'POST'])
# Will use JSON Only
# @renderer_classes([JSONRenderer, BrowsableAPIRenderer])
@renderer_classes((JSONRenderer,))
@permission_classes([permissions.IsAuthenticated])
def index(request):
    # try:
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode())
            result, detail = collector.parse_query(parser, data)
            return Response({"result": result,
                             "detail": detail
                             })
        except Exception as e:
            return Response({"result": False,
                            "detail": str(e)
                            })
    else:
        return Response({"result": "False",
                         "detail": "Use POST force, Luke..."
                        })




