import os
from pathlib import Path
from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import JsonResponse
from . import rfid_data

# Default is La belle lisse poire du prince de Motordu
DEFAULT_BOOK_ISBN = "9782070548064"
DEFAULT_VOICE = "default"


class SettingsView(TemplateView):
    template_name = "nabbookd/settings.html"

    def post(self, request, *args, **kwargs):
        return render(request, SettingsView.template_name)


class RFIDDataView(TemplateView):
    template_name = "nabbookd/rfid-data.html"

    @staticmethod
    def list_books():
        appdir = Path(os.path.dirname(os.path.abspath(__file__)))
        booksdir = appdir.joinpath("sounds", "nabbookd", "books")
        books = []
        for bookdir in booksdir.iterdir():
            book_item = {}
            book_item["isbn"] = bookdir.name
            title_file = bookdir.joinpath("title.txt")
            if title_file.is_file():
                with open(title_file) as f:
                    book_item["title"] = f.read().strip()
            voices = []
            for voicedir in bookdir.iterdir():
                if not voicedir.is_dir():
                    continue
                voice_item = {}
                voice_item["id"] = voicedir.name
                voicedesc_file = voicedir.joinpath("description.txt")
                if voicedesc_file.is_file():
                    with open(voicedesc_file) as f:
                        voice_item["description"] = f.read().strip()
                voices.append(voice_item)
            book_item["voices"] = voices
            books.append(book_item)
        return books

    def get(self, request, *args, **kwargs):
        """
        Unserialize RFID application data
        """
        context = self.get_context_data(**kwargs)
        data = request.GET.get("data", None)
        if data:
            unserialized = rfid_data.unserialize(data.encode())
            if unserialized:
                voice, book = unserialized
                context["book"] = book
                context["voice"] = voice
        context["books"] = RFIDDataView.list_books()
        return render(request, RFIDDataView.template_name, context=context)

    def post(self, request, *args, **kwargs):
        """
        Serialize RFID application data
        """
        book = DEFAULT_BOOK_ISBN
        voice = DEFAULT_VOICE
        if "book" in request.POST:
            book = request.POST["book"]
        if "voice" in request.POST:
            voice = request.POST["voice"]
        data = rfid_data.serialize(voice, book)
        data = data.decode("utf8")
        return JsonResponse({"data": data})
