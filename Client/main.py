import os
import sys
import ssl
import json
import socket
import hashlib
import webbrowser
import pandas as pd
from OpenSSL import crypto
from PyQt5.QtCore import Qt
from PyQt5 import QtWidgets
from PyQt5.uic import loadUi
from dotenv import load_dotenv
from PyQt5.QtWidgets import QDialog, QApplication, QTableWidgetItem, QAbstractItemView


################################################## LOG IN CLASS #######################################################

class LoginPage(QDialog):
    
    def __init__(self):
        super(LoginPage,self).__init__()
        loadUi(r'Client\pages\login_page.ui', self)
        self.login_button.clicked.connect(self.login_function)
        self.signup_button.clicked.connect(self.open_signup_page)
        self.linkedin_button.clicked.connect(self.open_linkedin)

    def login_function(self):
        username = str(self.username_line_edit.text())
        password = str(self.password_line_edit.text())
        enc_password = hashlib.sha256(password.encode()).hexdigest()
        
        self.username_line_edit.setText("")
        self.password_line_edit.setText("")

        if username != "" and password !="":
            global CLIENT, AES_KEY
            CLIENT = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                # WRAP SOCKET IN SSL
                context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                if str(os.getenv("ca_cert_required")) == "True": 
                    cert_file = str(os.getenv("ca_cert_file"))
                    key_file =  str(os.getenv("ca_key_file"))
                    context.load_cert_chain(certfile=cert_file, keyfile=key_file)
                    CLIENT.connect((os.getenv("pub_ip"), int(os.getenv("pub_port"))))
                    context.load_verify_locations(str(os.getenv("ca_verify_file")))
                else:
                    cert_file = str(os.getenv("gen_cert_file"))
                    key_file =  str(os.getenv("gen_key_file"))
                    generate_ssl_certificate(cert_file, key_file)
                    context.load_cert_chain(certfile=cert_file, keyfile=key_file)
                    context.verify_mode = ssl.CERT_NONE
                    CLIENT = context.wrap_socket(CLIENT)
                    CLIENT.connect((os.getenv("pub_ip"), int(os.getenv("pub_port"))))

                AES_KEY = key_exchange_handler()

                data = ["login", username, enc_password]
                send_data(data)

                response = receive_data()


                if response == True:
                    self.open_user_page()
                else:
                    close_connection()
    
            except: 
                print("Server Refused to Connect")
                try:
                    close_connection()
                except: pass
            
        else:
            print("Enter your credentials to login.")

    def open_linkedin(self):
        webbrowser.open('www.linkedin.com/in/kolby-macdonald')

    def open_signup_page(self):
        widget.removeWidget(login_window)
        widget.addWidget(signup_window)

    def open_user_page(self):
        user_window = UserPage()
        widget.addWidget(user_window)
        widget.removeWidget(login_window)

################################################## SIGN UP CLASS ######################################################

class SignUpPage(QDialog): 
    def __init__(self):
        super(SignUpPage,self).__init__()
        loadUi(r'Client\pages\signup_page.ui',self)
        self.submit_button.clicked.connect(self.signup_function)
        self.return_button.clicked.connect(self.open_login_page)

    def signup_function(self):
        username = self.username_line_edit.text()
        email = self.email_line_edit.text()
        password = self.password_line_edit.text()
        confirm_password = self.confirm_password_line_edit.text()
        print(f"username = {username} | email = {email} | password = {password} | confirm_password = {confirm_password}")
    
    def open_login_page(self):
        widget.addWidget(login_window)
        widget.removeWidget(signup_window)

##################################################### USER'S MAIN PAGE ################################################

class UserPage(QDialog):

    def __init__(self):
        super(UserPage, self).__init__()
        loadUi(r'Client\pages\user_page_test.ui', self)
        self.table_select_combobox.currentIndexChanged.connect(lambda: UserPage.request_handler(self, "update_loaded_table"))
        self.result_select_combobox.currentIndexChanged.connect(lambda: UserPage.request_handler(self, "update_loaded_table"))
        self.logout_button.clicked.connect(lambda: UserPage.request_handler(self, "log_out"))
        self.readwrite_radioButton.clicked.connect(lambda: UserPage.readwrite_table_control(self))
        self.lastfirst_pushButton.clicked.connect(lambda: UserPage.read_order(self))

        UserPage.request_handler(self, "get_init_data")

    #----------------------------------------------- CLIENT REQUEST FUNCTIONS #---------------------------------------

    def request_handler(self, request):

        if request == "get_init_data":
            data = [request]
            send_data(data)
            user_table_names = receive_data()
            self.user_write_table_names = user_table_names[0]
            self.user_read_table_names = user_table_names[1]
            UserPage.get_init_data(self)

        elif request == "update_loaded_table":
            if self.lastfirst_pushButton.text() == "Last":
                result_select = "-"+self.result_select_combobox.currentText()
            elif self.lastfirst_pushButton.text() == "First":
                result_select = self.result_select_combobox.currentText()

            data = [request, self.table_select_combobox.currentText(), result_select]
            send_data(data)
            table_data = receive_data()
            UserPage.update_table_view(self, table_data)
        
        elif request == "log_out":
            self.loaded_table_edit.clear()
            close_connection()
            user_window = self
            widget.addWidget(login_window)
            widget.removeWidget(user_window)

    #----------------------------------------------- CLIENT UI FUNCTIONS -------------------------------------------

    def get_init_data(self):

        if self.user_write_table_names != [] or self.user_read_table_names != []:
            self.table_select_combobox.addItems(self.user_write_table_names + self.user_read_table_names)
        else:
            self.readwrite_radioButton.setChecked(False)
            self.readwrite_radioButton.setEnabled(False)
            self.readwrite_radioButton.setText("No Selection")

    def update_table_view(self, table_data):
        self.loaded_table_edit.clear()
        
        if self.table_select_combobox.currentText() not in self.user_write_table_names:
            self.readwrite_radioButton.setChecked(False)
            self.readwrite_radioButton.setEnabled(False)
            self.readwrite_radioButton.setText("Locked Table")
            self.readwrite_table_control()
        elif self.table_select_combobox.currentText() in self.user_write_table_names:
            self.readwrite_radioButton.setText("Edit Mode")
            self.readwrite_radioButton.setEnabled(True)
            self.readwrite_table_control()

        if table_data != []:
            table_data = table_data[0]
            df = pd.DataFrame.from_dict(table_data)
            column_titles = list(df.columns.values)
            column_titles = [str(title) for title in column_titles]

            self.loaded_table_edit.setColumnCount(len(df.columns))
            self.loaded_table_edit.setRowCount(len(df.index))
            self.loaded_table_edit.setHorizontalHeaderLabels(column_titles)
            self.loaded_table_edit.resizeColumnsToContents()

            # Add extra 15 pixels on either side
            for column in range(self.loaded_table_edit.columnCount()):
                width = self.loaded_table_edit.columnWidth(column)
                self.loaded_table_edit.setColumnWidth(column, width + 30)
            
            for row in range(self.loaded_table_edit.rowCount()):
                item = QTableWidgetItem(str(row + 1))
                item.setTextAlignment(Qt.AlignCenter)  # Qt.AlignCenter
                self.loaded_table_edit.setVerticalHeaderItem(row, item)

            if self.lastfirst_pushButton.text() == "Last":
                for column, title in enumerate(column_titles):
                    for row, item in enumerate(reversed(df[title])):
                        item = str(item)
                        if item == 'None':
                            item = ''
                        self.loaded_table_edit.setItem(row, column, QTableWidgetItem(item))
            else:
                for column, title in enumerate(column_titles):
                    for row, item in enumerate(df[title]):
                        item = str(item)
                        if item == 'None':
                            item = ''
                        self.loaded_table_edit.setItem(row, column, QTableWidgetItem(item))
                
                
                

        else:
            print("No Acessable Tables Found")

    def read_order(self):
        if self.lastfirst_pushButton.text() == "Last":
            self.lastfirst_pushButton.setText("First")
        elif self.lastfirst_pushButton.text() == "First":
            self.lastfirst_pushButton.setText("Last")

        UserPage.request_handler(self, "update_loaded_table")
    
    def readwrite_table_control(self):
        if self.readwrite_radioButton.isChecked():
            self.loaded_table_edit.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)  # Enable editing
            self.loaded_table_edit.setSelectionMode(QAbstractItemView.ExtendedSelection)
        elif not self.readwrite_radioButton.isChecked():
            self.loaded_table_edit.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.loaded_table_edit.setSelectionMode(QAbstractItemView.NoSelection)
            self.loaded_table_edit.clearSelection()

######################################### SEND AND RECIEVE BUFFERED DATA ########################################

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


def aes_encrypt(json_data):
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    padded_json_data = pad(json_data.encode(), AES.block_size)
    enc_data = cipher.encrypt(padded_json_data)
    return enc_data

def aes_decrypt(enc_data):
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    padded_enc_data = cipher.decrypt(enc_data)
    json_data = unpad(padded_enc_data, AES.block_size)
    return json_data.decode()

def send_data(data):
    json_data = json.dumps(data)
    enc_data = aes_encrypt(json_data)
    data_length = len(enc_data)
    header = f"{data_length:<{15}}".encode('utf-8')

    chunk_size = 16380
    chunks = [enc_data[i:i+chunk_size] for i in range(0, data_length, chunk_size)]
    CLIENT.sendall(header)

    for chunk in chunks:
        #CLIENT.sendall(chunk.encode('utf-8'))
        CLIENT.sendall(chunk)


def receive_data():
    try:
        header = CLIENT.recv(15)
        if not header:
            return None

        data_length = int(header.strip())
        data = b""
        remaining_bytes = data_length

        while remaining_bytes > 0:
            chunk = CLIENT.recv(remaining_bytes)
            if not chunk:
                return None
            data += chunk
            remaining_bytes -= len(chunk)

        data = aes_decrypt(data)

        #json_data = json.loads(data.decode('utf-8'))
        json_data = json.loads(data)
        return json_data
    except:
        pass



def close_connection():
    global CLIENT
    data = ["log_out"]
    send_data(data)
    CLIENT.shutdown(socket.SHUT_RDWR)
    CLIENT.close()
    CLIENT = None
    
    #CLIENT = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


######################################## KEY EXCHANGE ########################################################

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

def key_exchange_handler():
    client_private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    client_public_key = client_private_key.public_key()

    client_private_pem = client_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    client_public_pem = client_public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    CLIENT.sendall(client_public_pem)
    encrypted_key = CLIENT.recv(1024)
    client_private_pem = serialization.load_pem_private_key(client_private_pem, password=None)
    aes_key = client_private_pem.decrypt(
        encrypted_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return aes_key
    

######################################### SECURE SOCKET LAYER ########################################################

def generate_ssl_certificate(cert_file, key_file):
    # Create a new key pair
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)
    
    # Create a self-signed certificate
    cert = crypto.X509()
    cert.get_subject().CN = "AvailData"
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(1 * 24 * 60 * 60) #24 Hours 
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, "sha256")
    
    # Save the certificate and private key to files
    with open(cert_file, "wb") as cert_file:
        cert_file.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    
    with open(key_file, "wb") as key_file:
        key_file.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))

    return(cert_file, key_file)

######################################### MAIN STARTUP SCRIPT #########################################################

load_dotenv()
app=QApplication(sys.argv)
widget=QtWidgets.QStackedWidget()
login_window = LoginPage()
signup_window = SignUpPage()
widget.setWindowTitle("[ AvailData ]")
widget.addWidget(login_window)
widget.resize(1080,720)
widget.setMaximumWidth(1920)
widget.setMaximumHeight(1080)
widget.show()
app.exec_()