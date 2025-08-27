import sys
import subprocess
import threading
import json
import os
import time
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.modalview import ModalView
from kivy.uix.togglebutton import ToggleButton
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty, ObjectProperty
from kivy.config import Config

# تنظیم اندازه پنجره
Config.set('graphics', 'width', '900')
Config.set('graphics', 'height', '700')
Config.set('graphics', 'resizable', '1')

class VPNItem(BoxLayout):
    name = StringProperty('')
    selected = BooleanProperty(False)
    
    def __init__(self, name, on_select_callback, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.on_select_callback = on_select_callback
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = 40
        
        self.label = Label(text=name, size_hint_x=0.8)
        self.add_widget(self.label)
        
        self.select_btn = ToggleButton(text='Select', group='vpn_list', 
                                     size_hint_x=0.2, on_press=self.on_select)
        self.add_widget(self.select_btn)
    
    def on_select(self, instance):
        if instance.state == 'down':
            self.selected = True
            self.on_select_callback(self.name)

class SSHVPNManager(App):
    ssh_process = None
    is_connected = BooleanProperty(False)
    status_text = StringProperty('Ready to connect')
    output_text = StringProperty('')
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.saved_vpns = {}
        self.current_vpn = None
        self.original_proxy_settings = None
        
        # مسیر فایل ذخیره‌سازی
        self.saved_vpns_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_vpns.json")
        self.load_saved_vpns()
    
    def load_saved_vpns(self):
        """Load saved VPN configurations from file"""
        if os.path.exists(self.saved_vpns_file):
            try:
                with open(self.saved_vpns_file, 'r', encoding='utf-8') as f:
                    self.saved_vpns = json.load(f)
            except Exception as e:
                print(f"Error loading VPNs: {e}")
                self.saved_vpns = {}
    
    def save_vpns(self):
        """Save VPN configurations to file"""
        try:
            with open(self.saved_vpns_file, 'w', encoding='utf-8') as f:
                json.dump(self.saved_vpns, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving VPNs: {e}")
    
    def build(self):
        self.title = "SSH VPN Manager"
        
        # Main layout
        main_layout = BoxLayout(orientation='horizontal', padding=10, spacing=10)
        
        # Left panel for saved VPNs
        left_panel = BoxLayout(orientation='vertical', size_hint_x=0.3, spacing=10)
        
        left_panel.add_widget(Label(text='Saved VPNs:', size_hint_y=0.05))
        
        # Scroll view for VPN list
        scroll_view = ScrollView(size_hint_y=0.7)
        self.vpn_list_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=5)
        self.vpn_list_layout.bind(minimum_height=self.vpn_list_layout.setter('height'))
        scroll_view.add_widget(self.vpn_list_layout)
        left_panel.add_widget(scroll_view)
        
        # Save name input
        save_layout = BoxLayout(orientation='horizontal', size_hint_y=0.1, spacing=5)
        save_layout.add_widget(Label(text='Save as:', size_hint_x=0.3))
        self.save_name_input = TextInput(hint_text='Enter VPN name', multiline=False, size_hint_x=0.7)
        save_layout.add_widget(self.save_name_input)
        left_panel.add_widget(save_layout)
        
        # Save and Delete buttons
        btn_layout = BoxLayout(orientation='horizontal', size_hint_y=0.1, spacing=5)
        self.save_btn = Button(text='Save VPN', on_press=self.save_current_vpn)
        self.delete_btn = Button(text='Delete VPN', on_press=self.delete_vpn)
        btn_layout.add_widget(self.save_btn)
        btn_layout.add_widget(self.delete_btn)
        left_panel.add_widget(btn_layout)
        
        left_panel.add_widget(BoxLayout(size_hint_y=0.05))  # Spacer
        
        # Right panel for connection details
        right_panel = BoxLayout(orientation='vertical', size_hint_x=0.7, spacing=10)
        
        # Connection details form
        form_layout = GridLayout(cols=2, spacing=10, size_hint_y=0.5)
        
        form_layout.add_widget(Label(text='Connection Type:'))
        self.connection_type = Spinner(
            text='SSH Tunnel',
            values=['SSH Tunnel', 'Full VPN (sshuttle)'],
            size_hint_y=None, height=30
        )
        form_layout.add_widget(self.connection_type)
        
        form_layout.add_widget(Label(text='Username:'))
        self.username_input = TextInput(hint_text='Enter username', multiline=False, size_hint_y=None, height=30)
        form_layout.add_widget(self.username_input)
        
        form_layout.add_widget(Label(text='IP Address:'))
        self.ip_input = TextInput(hint_text='Enter server IP address', multiline=False, size_hint_y=None, height=30)
        form_layout.add_widget(self.ip_input)
        
        form_layout.add_widget(Label(text='Password:'))
        self.password_input = TextInput(hint_text='Enter password', password=True, multiline=False, size_hint_y=None, height=30)
        form_layout.add_widget(self.password_input)
        
        form_layout.add_widget(Label(text='Port:'))
        self.port_input = TextInput(text='22', hint_text='SSH port (default: 22)', multiline=False, size_hint_y=None, height=30)
        form_layout.add_widget(self.port_input)
        
        form_layout.add_widget(Label(text='SSH Options:'))
        self.ssh_options = TextInput(
            text='-o StrictHostKeyChecking=no -o ServerAliveInterval=60',
            hint_text='Additional SSH options', 
            multiline=False, size_hint_y=None, height=30
        )
        form_layout.add_widget(self.ssh_options)
        
        form_layout.add_widget(Label(text='SOCKS Port:'))
        self.socks_port_input = TextInput(text='1080', hint_text='SOCKS proxy port', multiline=False, size_hint_y=None, height=30)
        form_layout.add_widget(self.socks_port_input)
        
        right_panel.add_widget(form_layout)
        
        # Buttons
        btn_layout2 = BoxLayout(orientation='horizontal', size_hint_y=0.1, spacing=10)
        self.connect_btn = Button(text='Connect VPN', on_press=self.toggle_connection)
        self.ping_btn = Button(text='Ping Server', on_press=self.ping_server)
        self.set_proxy_btn = Button(text='Set System Proxy', on_press=self.set_system_proxy)
        self.auto_proxy_btn = Button(text='Auto System Proxy', on_press=self.toggle_auto_proxy)
        btn_layout2.add_widget(self.connect_btn)
        btn_layout2.add_widget(self.ping_btn)
        btn_layout2.add_widget(self.set_proxy_btn)
        btn_layout2.add_widget(self.auto_proxy_btn)
        right_panel.add_widget(btn_layout2)
        
        # Status bar
        self.status_label = Label(text=self.status_text, size_hint_y=0.05)
        right_panel.add_widget(self.status_label)
        
        # Output console
        output_scroll = ScrollView(size_hint_y=0.35)
        self.output_label = Label(text=self.output_text, size_hint_y=None, valign='top')
        self.output_label.bind(texture_size=self.output_label.setter('size'))
        output_scroll.add_widget(self.output_label)
        right_panel.add_widget(output_scroll)
        
        # Add panels to main layout
        main_layout.add_widget(left_panel)
        main_layout.add_widget(right_panel)
        
        # Load saved VPNs
        self.refresh_vpn_list()
        
        return main_layout
    
    def refresh_vpn_list(self):
        """Refresh the list of saved VPNs"""
        self.vpn_list_layout.clear_widgets()
        for vpn_name in self.saved_vpns.keys():
            item = VPNItem(vpn_name, self.load_vpn_config)
            self.vpn_list_layout.add_widget(item)
    
    def append_output(self, message):
        """Append message to output console"""
        self.output_text += message + '\n'
        self.output_label.text = self.output_text
    
    def update_status(self, message, is_error=False):
        """Update status bar with message"""
        self.status_text = message
        self.status_label.text = message
        if is_error:
            self.status_label.color = (1, 0, 0, 1)  # Red for errors
        else:
            self.status_label.color = (0, 0, 0, 1)  # Black for normal
    
    def save_current_vpn(self, instance):
        """Save current configuration as a VPN"""
        vpn_name = self.save_name_input.text.strip()
        if not vpn_name:
            self.show_popup("Warning", "Please enter a name for the VPN")
            return
            
        username = self.username_input.text.strip()
        ip = self.ip_input.text.strip()
        password = self.password_input.text
        port = self.port_input.text.strip()
        ssh_options = self.ssh_options.text.strip()
        socks_port = self.socks_port_input.text.strip()
        connection_type = self.connection_type.text
        
        if not all([username, ip, password]):
            self.show_popup("Warning", "Please fill all required fields")
            return
            
        # Save VPN configuration
        self.saved_vpns[vpn_name] = {
            'username': username,
            'ip': ip,
            'password': password,
            'port': port,
            'ssh_options': ssh_options,
            'socks_port': socks_port,
            'connection_type': connection_type
        }
        
        self.save_vpns()
        self.refresh_vpn_list()
        self.append_output(f"VPN '{vpn_name}' saved successfully!")
    
    def delete_vpn(self, instance):
        """Delete selected VPN"""
        if not self.current_vpn:
            self.show_popup("Warning", "Please select a VPN to delete")
            return
            
        vpn_name = self.current_vpn
        self.show_confirm_popup("Confirm Delete", 
                              f"Are you sure you want to delete '{vpn_name}'?",
                              self.confirm_delete)
    
    def confirm_delete(self):
        """Confirm and delete VPN"""
        if self.current_vpn:
            del self.saved_vpns[self.current_vpn]
            self.save_vpns()
            self.refresh_vpn_list()
            self.append_output(f"VPN '{self.current_vpn}' deleted successfully!")
            self.current_vpn = None
    
    def load_vpn_config(self, vpn_name):
        """Load VPN configuration from selected item"""
        self.current_vpn = vpn_name
        config = self.saved_vpns.get(vpn_name)
        
        if config:
            self.username_input.text = config.get('username', '')
            self.ip_input.text = config.get('ip', '')
            self.password_input.text = config.get('password', '')
            self.port_input.text = config.get('port', '22')
            self.ssh_options.text = config.get('ssh_options', '-o StrictHostKeyChecking=no -o ServerAliveInterval=60')
            self.socks_port_input.text = config.get('socks_port', '1080')
            self.save_name_input.text = vpn_name
            
            # Set connection type if available
            connection_type = config.get('connection_type', 'SSH Tunnel')
            if connection_type in self.connection_type.values:
                self.connection_type.text = connection_type
                
            self.append_output(f"Loaded VPN configuration: {vpn_name}")
    
    def ping_server(self, instance):
        """Ping the server to check connectivity"""
        ip = self.ip_input.text.strip()
        if not ip:
            self.show_popup("Warning", "Please enter an IP address")
            return
            
        self.append_output(f"Pinging {ip}...")
        self.update_status(f"Pinging {ip}...")
        
        # Run ping in a separate thread to avoid blocking the UI
        threading.Thread(target=self.execute_ping, args=(ip,), daemon=True).start()
    
    def execute_ping(self, ip):
        """Execute ping command"""
        try:
            # For Windows use 'ping -n 4', for Linux/Mac use 'ping -c 4'
            command = ['ping', '-c', '4', ip] if sys.platform != 'win32' else ['ping', '-n', '4', ip]
            
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self.append_output("Ping successful! Server is reachable.")
                Clock.schedule_once(lambda dt: self.update_status("Ping successful"))
            else:
                self.append_output("Ping failed! Server may be unreachable.")
                self.append_output(f"Error: {result.stderr}")
                Clock.schedule_once(lambda dt: self.update_status("Ping failed", True))
                
        except subprocess.TimeoutExpired:
            self.append_output("Ping timeout! Server may be unreachable.")
            Clock.schedule_once(lambda dt: self.update_status("Ping timeout", True))
        except Exception as e:
            self.append_output(f"Ping error: {str(e)}")
            Clock.schedule_once(lambda dt: self.update_status("Ping error", True))
    
    def toggle_connection(self, instance):
        """Toggle SSH connection"""
        if self.is_connected:
            self.disconnect_ssh()
        else:
            self.connect_ssh()
    
    def set_system_proxy(self, instance):
        """Set system proxy to use SOCKS proxy"""
        if not self.is_connected:
            self.show_popup("Warning", "Please connect to VPN first")
            return
            
        try:
            socks_port = int(self.socks_port_input.text.strip())
        except ValueError:
            socks_port = 1080
            
        if sys.platform == 'win32':
            # Windows proxy settings
            try:
                import winreg
                # Set proxy settings in registry
                reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                key = winreg.OpenKey(reg, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 0, winreg.KEY_WRITE)
                
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"socks=127.0.0.1:{socks_port}")
                
                winreg.CloseKey(key)
                self.append_output("System proxy set to use SOCKS on 127.0.0.1:" + str(socks_port))
                self.append_output("Note: Some applications may need to be restarted to use the proxy")
            except Exception as e:
                self.append_output(f"Error setting Windows proxy: {str(e)}")
        else:
            # Linux - set system proxy automatically
            self.set_linux_system_proxy(socks_port)
    
    def toggle_auto_proxy(self, instance):
        """Toggle automatic system proxy setting"""
        if not self.is_connected:
            self.show_popup("Warning", "Please connect to VPN first")
            return
            
        try:
            socks_port = int(self.socks_port_input.text.strip())
        except ValueError:
            socks_port = 1080
            
        if sys.platform != 'win32':
            self.set_linux_auto_proxy(socks_port)
    
    def set_linux_system_proxy(self, socks_port):
        """Set system proxy on Linux automatically"""
        try:
            # Try different methods for different Linux desktop environments
            
            # Method 1: GNOME using gsettings
            if self.is_command_available('gsettings'):
                try:
                    # Save current settings
                    self.backup_gnome_proxy_settings()
                    
                    # Set SOCKS proxy
                    subprocess.run([
                        'gsettings', 'set', 'org.gnome.system.proxy', 'mode', 'manual'
                    ], check=True)
                    
                    subprocess.run([
                        'gsettings', 'set', 'org.gnome.system.proxy.socks', 'host', '127.0.0.1'
                    ], check=True)
                    
                    subprocess.run([
                        'gsettings', 'set', 'org.gnome.system.proxy.socks', 'port', str(socks_port)
                    ], check=True)
                    
                    self.append_output("GNOME system proxy configured successfully!")
                    self.append_output(f"SOCKS Proxy: 127.0.0.1:{socks_port}")
                    return
                except subprocess.CalledProcessError as e:
                    self.append_output(f"GNOME proxy setting failed: {e}")
            
            # Method 2: Environment variables (system-wide)
            try:
                # Set environment variables in /etc/environment
                with open('/etc/environment', 'a') as f:
                    f.write(f'\nhttp_proxy="socks5://127.0.0.1:{socks_port}"\n')
                    f.write(f'https_proxy="socks5://127.0.0.1:{socks_port}"\n')
                    f.write(f'ftp_proxy="socks5://127.0.0.1:{socks_port}"\n')
                    f.write(f'all_proxy="socks5://127.0.0.1:{socks_port}"\n')
                
                self.append_output("System environment proxy configured in /etc/environment")
                self.append_output("Please reboot or log out/in for changes to take effect")
            except PermissionError:
                self.append_output("Need root privileges to modify /etc/environment")
                self.append_output("Run with sudo or manually set environment variables")
            
            # Method 3: Provide manual instructions
            self.append_output("Manual configuration:")
            self.append_output(f"Export these variables in your shell:")
            self.append_output(f"export http_proxy=socks5://127.0.0.1:{socks_port}")
            self.append_output(f"export https_proxy=socks5://127.0.0.1:{socks_port}")
            self.append_output(f"export ALL_PROXY=socks5://127.0.0.1:{socks_port}")
            
        except Exception as e:
            self.append_output(f"Error setting Linux proxy: {str(e)}")
    
    def set_linux_auto_proxy(self, socks_port):
        """Advanced automatic proxy configuration for Linux"""
        try:
            # Method 1: NetworkManager configuration
            if self.is_command_available('nmcli'):
                try:
                    # Create a new NetworkManager connection for proxy
                    connection_name = f"ssh-vpn-proxy-{socks_port}"
                    
                    subprocess.run([
                        'nmcli', 'connection', 'add', 'type', 'proxy',
                        'con-name', connection_name,
                        'proxy.method', 'socks5',
                        'proxy.host', '127.0.0.1',
                        'proxy.port', str(socks_port),
                        'ipv4.method', 'auto'
                    ], check=True)
                    
                    # Activate the connection
                    subprocess.run([
                        'nmcli', 'connection', 'up', connection_name
                    ], check=True)
                    
                    self.append_output(f"NetworkManager proxy connection '{connection_name}' activated!")
                    return
                except subprocess.CalledProcessError as e:
                    self.append_output(f"NetworkManager configuration failed: {e}")
            
            # Method 2: Create proxy auto-config (PAC) file
            pac_content = f'''
function FindProxyForURL(url, host) {{
    return "SOCKS5 127.0.0.1:{socks_port}";
}}
'''
            
            pac_file = os.path.expanduser(f'~/.ssh-vpn-proxy-{socks_port}.pac')
            with open(pac_file, 'w') as f:
                f.write(pac_content)
            
            self.append_output(f"PAC file created: {pac_file}")
            self.append_output("Configure your browser to use this PAC file:")
            self.append_output(f"file://{pac_file}")
            
            # Method 3: Set for specific applications
            self.append_output("\nFor specific applications:")
            self.append_output(f"curl --socks5 127.0.0.1:{socks_port} http://example.com")
            self.append_output(f"wget -e use_proxy=yes -e socks_proxy=127.0.0.1:{socks_port} http://example.com")
            
        except Exception as e:
            self.append_output(f"Error in auto proxy configuration: {str(e)}")
    
    def backup_gnome_proxy_settings(self):
        """Backup current GNOME proxy settings"""
        try:
            if not self.original_proxy_settings:
                self.original_proxy_settings = {}
                
                # Get current proxy mode
                result = subprocess.run([
                    'gsettings', 'get', 'org.gnome.system.proxy', 'mode'
                ], capture_output=True, text=True, check=True)
                self.original_proxy_settings['mode'] = result.stdout.strip()
                
                # Get SOCKS settings
                result = subprocess.run([
                    'gsettings', 'get', 'org.gnome.system.proxy.socks', 'host'
                ], capture_output=True, text=True, check=True)
                self.original_proxy_settings['socks_host'] = result.stdout.strip()
                
                result = subprocess.run([
                    'gsettings', 'get', 'org.gnome.system.proxy.socks', 'port'
                ], capture_output=True, text=True, check=True)
                self.original_proxy_settings['socks_port'] = result.stdout.strip()
                
                self.append_output("GNOME proxy settings backed up")
                
        except Exception as e:
            self.append_output(f"Could not backup GNOME settings: {e}")
    
    def restore_gnome_proxy_settings(self):
        """Restore original GNOME proxy settings"""
        try:
            if self.original_proxy_settings:
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy', 'mode',
                    self.original_proxy_settings['mode']
                ], check=True)
                
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy.socks', 'host',
                    self.original_proxy_settings['socks_host']
                ], check=True)
                
                subprocess.run([
                    'gsettings', 'set', 'org.gnome.system.proxy.socks', 'port',
                    self.original_proxy_settings['socks_port']
                ], check=True)
                
                self.append_output("GNOME proxy settings restored")
                
        except Exception as e:
            self.append_output(f"Could not restore GNOME settings: {e}")
    
    def is_command_available(self, command):
        """Check if a command is available in the system"""
        try:
            subprocess.run([command, '--help'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def connect_ssh(self):
        """Establish SSH connection"""
        username = self.username_input.text.strip()
        ip = self.ip_input.text.strip()
        password = self.password_input.text
        port = self.port_input.text.strip()
        ssh_options = self.ssh_options.text.strip()
        connection_type = self.connection_type.text
        
        try:
            socks_port = int(self.socks_port_input.text.strip())
        except ValueError:
            socks_port = 1080
            
        if not all([username, ip, password]):
            self.show_popup("Warning", "Please fill all required fields")
            return
            
        try:
            port = int(port) if port else 22
        except ValueError:
            self.show_popup("Warning", "Port must be a valid number")
            return
            
        self.append_output(f"Connecting to {username}@{ip}:{port}...")
        self.update_status("Connecting...")
        
        # Connect in a separate thread
        threading.Thread(target=self.execute_ssh_connection, 
                        args=(ip, port, username, password, ssh_options, connection_type, socks_port), 
                        daemon=True).start()
    
    def execute_ssh_connection(self, ip, port, username, password, ssh_options, connection_type, socks_port):
        """Execute SSH connection"""
        try:
            # Prepare SSH command based on connection type
            if connection_type == "Full VPN (sshuttle)":
                # Check if sshuttle is available
                try:
                    subprocess.run(["sshuttle", "--version"], capture_output=True, check=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    self.append_output("sshuttle not found. Please install it first.")
                    self.append_output("On Ubuntu/Debian: sudo apt install sshuttle")
                    self.append_output("Or using pip: pip install sshuttle")
                    Clock.schedule_once(lambda dt: self.update_status("sshuttle not installed", True))
                    return
                
                # Build sshuttle command
                cmd = [
                    "sshuttle",
                    "-r", f"{username}@{ip}:{port}",
                    "-e", f"ssh {ssh_options}",
                    "--ssh-cmd", f"sshpass -p {password} ssh",
                    "0.0.0.0/0",
                    "--daemon"
                ]
            else:
                # Standard SSH tunnel (SOCKS proxy)
                cmd = [
                    "sshpass", "-p", password, "ssh",
                    *ssh_options.split(),
                    "-D", str(socks_port),  # SOCKS proxy on specified port
                    "-N",  # No remote command
                    "-p", str(port),
                    f"{username}@{ip}"
                ]
            
            self.append_output(f"Executing: {' '.join(cmd)}")
            
            # Start SSH process
            self.ssh_process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL
            )
            
            # Wait a moment to see if connection succeeds
            time.sleep(3)
            
            # Check if process is still running
            if self.ssh_process.poll() is None:
                self.is_connected = True
                self.append_output("SSH VPN connection established successfully!")
                
                if connection_type == "Full VPN (sshuttle)":
                    self.append_output("Full VPN tunnel active using sshuttle")
                    self.append_output("All traffic is now routed through the VPN")
                else:
                    self.append_output(f"SOCKS proxy running on localhost:{socks_port}")
                    self.append_output("Configure your browser or system to use this proxy")
                
                Clock.schedule_once(lambda dt: self.update_status("Connected"))
            else:
                # Connection failed
                stdout, stderr = self.ssh_process.communicate()
                error_msg = stderr.decode() if stderr else "Unknown error"
                self.append_output(f"Connection failed: {error_msg}")
                Clock.schedule_once(lambda dt: self.update_status("Connection failed", True))
                self.ssh_process = None
                
        except Exception as e:
            self.append_output(f"Connection error: {str(e)}")
            Clock.schedule_once(lambda dt: self.update_status("Connection error", True))
            
        finally:
            # Update UI in main thread
            Clock.schedule_once(lambda dt: setattr(self, 'is_connected', self.is_connected))
    
    def disconnect_ssh(self):
        """Disconnect SSH connection"""
        if self.ssh_process:
            self.append_output("Disconnecting SSH VPN...")
            self.update_status("Disconnecting...")
            
            # Terminate SSH process
            try:
                self.ssh_process.terminate()
                self.ssh_process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    self.ssh_process.kill()
                except:
                    pass
            except Exception as e:
                self.append_output(f"Error during disconnect: {str(e)}")
            
            self.ssh_process = None
            self.is_connected = False
            self.append_output("SSH VPN disconnected")
            
            # Reset system proxy
            if sys.platform == 'win32':
                try:
                    import winreg
                    reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                    key = winreg.OpenKey(reg, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 0, winreg.KEY_WRITE)
                    winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
                    winreg.CloseKey(key)
                    self.append_output("System proxy disabled")
                except:
                    pass
            else:
                # Restore GNOME proxy settings on Linux
                self.restore_gnome_proxy_settings()
                self.append_output("Linux proxy settings restored")
            
            self.update_status("Disconnected")
    
    def show_popup(self, title, message):
        """Show a simple popup message"""
        popup = Popup(title=title,
                     content=Label(text=message),
                     size_hint=(0.8, 0.4))
        popup.open()
    
    def show_confirm_popup(self, title, message, callback):
        """Show a confirmation popup"""
        content = BoxLayout(orientation='vertical')
        content.add_widget(Label(text=message))
        
        btn_layout = BoxLayout(size_hint_y=0.4, spacing=10)
        yes_btn = Button(text='Yes', on_press=lambda x: self.confirm_popup_action(popup, callback))
        no_btn = Button(text='No', on_press=lambda x: popup.dismiss())
        btn_layout.add_widget(yes_btn)
        btn_layout.add_widget(no_btn)
        
        content.add_widget(btn_layout)
        
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.4))
        popup.open()
    
    def confirm_popup_action(self, popup, callback):
        """Handle confirmation popup action"""
        popup.dismiss()
        callback()
    
    def on_is_connected(self, instance, value):
        """Update UI when connection status changes"""
        if value:
            self.connect_btn.text = "Disconnect VPN"
            self.connect_btn.background_color = (1, 0.5, 0.5, 1)  # Light red
        else:
            self.connect_btn.text = "Connect VPN"
            self.connect_btn.background_color = (0.5, 1, 0.5, 1)  # Light green

if __name__ == "__main__":
    # Check if sshpass is available
    try:
        subprocess.run(["sshpass", "-V"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("sshpass not found. Please install it for password authentication.")
        print("On Ubuntu/Debian: sudo apt install sshpass")
    
    SSHVPNManager().run()