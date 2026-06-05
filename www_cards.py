import io
import sys

from flask import Flask, request, send_file
import haed_card

app = Flask(__name__)
application = app


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            return redirect(request.url)
        if file:
            (doc, name) = haed_card.make_card_from_stream(file.read())
            return send_file(
                io.BytesIO(doc.tobytes()),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'{name}.pdf')
    return '''
    <!doctype html>
    <title>HAED chart to thread cards</title>
    <h1>Select chart pdf</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file accept='.pdf'>
      <input type=submit value=Make_Card>
    </form>
    '''

if __name__ == "__main__":
    app.run()
