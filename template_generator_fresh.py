import os
import json
import requests
from datetime import datetime
import openai
from flask import Flask, render_template, request, jsonify, send_file
import base64
from PIL import Image
import io
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'your-openai-key-here')
DALLE_API_KEY = os.getenv('DALLE_API_KEY', 'your-dalle-key-here')
SENDY_API_KEY = 'WEbCbmHWj7N774gWVVsD'

# Template structure
KEMISEMIL_TEMPLATE = {
    'colors': {
        'primary': '#00CED1',  # Turquoise
        'secondary': '#FF6B35',  # Orange
        'accent': '#FFD700',  # Yellow
        'text': '#333333',  # Dark gray
        'background': '#FFFFFF'  # White
    },
    'fonts': {
        'primary': 'arial, "helvetica neue", helvetica, sans-serif'
    }
}

class TemplateGenerator:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
    def generate_email_content(self, prompt):
        """Generate email content using OpenAI"""
        system_prompt = """You are a Bahamian email marketing expert. Create SHORT, CLEAN email content that:
        - Uses Bahamian tone and local references (Bay Street, straw markets, regattas, Junkanoo, conch salad)
        - Is 4-5 lines maximum - keep it short and sweet
        - Use single space after periods, no double spacing
        - Include 2-3 relevant emojis maximum
        - Focus on the specific business/promotion mentioned
        - Has a clear call-to-action
        - No long paragraphs or run-on sentences
        - Use "Bey!" instead of "Hey" in greetings for authentic Bahamian tone
        
        Return the content in JSON format with these fields:
        {
            "subject_line": "Email subject line",
            "hero_title": "Main headline (max 3 words)",
            "greeting": "Personal greeting with [Name,fallback=there]",
            "main_content": "Main body content - 4-5 short lines maximum, separated by &nbsp;",
            "cta_text": "Call to action button text",
            "cta_url": "Call to action URL",
            "urgency_text": "Urgency message if applicable",
            "offer_details": "Specific offer details if applicable"
        }"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Create an email campaign for: {prompt}"}
                ],
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
        except openai.RateLimitError as e:
            print(f"Rate limit exceeded: {e}")
            return self.get_fallback_content(prompt)
        except openai.QuotaExceededError as e:
            print(f"Quota exceeded: {e}")
            return self.get_fallback_content(prompt)
        except openai.APIError as e:
            print(f"OpenAI API error: {e}")
            # Try with GPT-3.5-turbo as fallback
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Create an email campaign for: {prompt}"}
                    ],
                    temperature=0.7
                )
                content = response.choices[0].message.content
                return json.loads(content)
            except:
                return self.get_fallback_content(prompt)
        except Exception as e:
            print(f"Error generating content: {e}")
            return self.get_fallback_content(prompt)
    
    def generate_image_prompt(self, content):
        """Generate image prompt for DALL-E"""
        system_prompt = """You are an expert at creating image prompts for email marketing. Create a detailed, specific prompt for DALL-E that will generate a professional, engaging image for an email campaign.
        
        The image should:
        - Be landscape orientation
        - Be photo-realistic
        - Have bright, professional lighting
        - Include Bahamian elements when relevant
        - Be suitable for email marketing
        - Have no text overlay
        - Be visually appealing and modern
        
        Format your response as a detailed image description that DALL-E can understand."""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Create an image prompt for this email content: {json.dumps(content, indent=2)}"}
                ],
                temperature=0.8
            )
            
            return response.choices[0].message.content
        except openai.RateLimitError as e:
            print(f"Rate limit exceeded for image prompt: {e}")
            return "Professional email marketing image with modern design, bright lighting, and engaging visual elements"
        except openai.QuotaExceededError as e:
            print(f"Quota exceeded for image prompt: {e}")
            return "Professional email marketing image with modern design, bright lighting, and engaging visual elements"
        except openai.APIError as e:
            print(f"OpenAI API error for image prompt: {e}")
            return "Professional email marketing image with modern design, bright lighting, and engaging visual elements"
        except Exception as e:
            print(f"Error generating image prompt: {e}")
            return "Professional email marketing image with modern design, bright lighting, and engaging visual elements"
    
    def generate_image(self, prompt):
        """Generate image using DALL-E"""
        try:
            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            
            image_url = response.data[0].url
            return self.download_and_process_image(image_url)
        except openai.RateLimitError as e:
            print(f"Rate limit exceeded for image generation: {e}")
            return None
        except openai.QuotaExceededError as e:
            print(f"Quota exceeded for image generation: {e}")
            return None
        except openai.APIError as e:
            print(f"OpenAI API error for image generation: {e}")
            return None
        except Exception as e:
            print(f"Error generating image: {e}")
            return None
    
    def download_and_process_image(self, image_url):
        """Download and process the generated image"""
        try:
            response = requests.get(image_url)
            if response.status_code == 200:
                # Open image with PIL
                image = Image.open(io.BytesIO(response.content))
                
                # Always resize to 560px width regardless of original size
                target_width = 560
                
                if image.width != target_width:
                    ratio = target_width / image.width
                    new_height = int(image.height * ratio)
                    image = image.resize((target_width, new_height), Image.Resampling.LANCZOS)
                
                # Convert to RGB if necessary
                if image.mode in ('RGBA', 'LA', 'P'):
                    image = image.convert('RGB')
                
                # Check original image size to determine compression quality
                original_size = len(response.content)
                print(f"📸 Processing image: {original_size:,} bytes, {image.width}x{image.height}")
                
                if original_size > 1024 * 1024:  # Over 1MB
                    print(f"📸 Large image detected: {original_size:,} bytes, using aggressive compression...")
                    quality = 60
                else:
                    quality = 70
                
                # Save as JPEG with appropriate compression
                output_buffer = io.BytesIO()
                image.save(output_buffer, format='JPEG', quality=quality, optimize=True)
                output_buffer.seek(0)
                
                # Check final size
                final_size = len(output_buffer.getvalue())
                print(f"✅ Image processed: {final_size:,} bytes (quality: {quality})")
                
                # If still too large, try even more aggressive compression
                if final_size > 300 * 1024:  # Over 300KB (more aggressive)
                    print(f"⚠️ Image still large: {final_size:,} bytes, trying ultra compression...")
                    output_buffer = io.BytesIO()
                    image.save(output_buffer, format='JPEG', quality=30, optimize=True)
                    output_buffer.seek(0)
                    final_size = len(output_buffer.getvalue())
                    print(f"✅ Ultra compressed: {final_size:,} bytes")
                    
                    # If still too large, try extreme compression
                    if final_size > 300 * 1024:
                        print(f"⚠️ Image still large: {final_size:,} bytes, trying extreme compression...")
                        output_buffer = io.BytesIO()
                        image.save(output_buffer, format='JPEG', quality=20, optimize=True)
                        output_buffer.seek(0)
                        final_size = len(output_buffer.getvalue())
                        print(f"✅ Extreme compressed: {final_size:,} bytes")
                        
                        # If still too large, use placeholder
                        if final_size > 300 * 1024:
                            print(f"⚠️ Image still too large: {final_size:,} bytes, using placeholder")
                            return None
                
                # Convert to base64 for web display
                image_data = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
                return f"data:image/jpeg;base64,{image_data}"
            
            print(f"❌ Failed to download image: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            print(f"❌ Error processing image: {e}")
            return None
    
    def get_fallback_content(self, prompt):
        """Fallback content if AI generation fails"""
        return {
            "subject_line": f"Special Offer: {prompt}",
            "hero_title": "SPECIAL OFFER",
            "greeting": "Hey Bey [Name,fallback=there]! 🎉",
            "main_content": f"Check out this amazing deal! {prompt}",
            "cta_text": "LEARN MORE",
            "cta_url": "https://www.kemis.net",
            "urgency_text": "Limited time offer!",
            "offer_details": "Don't miss out!"
        }
    
    def send_to_sendy(self, content, html_template, filename):
        """Send template to Sendy API"""
        try:
            # First, test if Sendy is accessible
            test_url = "https://kemis.net/sendy/"
            try:
                test_response = requests.get(test_url, timeout=10)
                print(f"🔍 Sendy accessibility test: {test_response.status_code}")
            except Exception as e:
                print(f"⚠️ Sendy accessibility test failed: {e}")
                return {
                    'success': False,
                    'error': f'Sendy installation not accessible: {str(e)}'
                }
            
            # Test API key with a simple request
            print(f"🔑 Testing API key: {SENDY_API_KEY[:8]}...")
            test_api_url = "https://kemis.net/sendy/api/subscribers.php"
            test_api_data = {
                'api_key': SENDY_API_KEY,
                'list': 'DU0p7BsJdnwE0MXNZusbMQ'
            }
            
            try:
                api_test_response = requests.post(test_api_url, data=test_api_data, timeout=10)
                print(f"🔑 API key test: {api_test_response.status_code} - {api_test_response.text[:100]}...")
            except Exception as e:
                print(f"⚠️ API key test failed: {e}")
            # Try different Sendy API endpoints
            sendy_endpoints = [
                "https://kemis.net/sendy/api/campaigns/create.php",
                "https://kemis.net/sendy/api/campaigns/create",
                "https://kemis.net/sendy/api/campaigns.php",
                "https://kemis.net/sendy/api/campaigns"
            ]
            
            # Generate campaign name from subject line + date
            from datetime import datetime
            now = datetime.now()
            date_only = now.strftime("%m-%d-%Y")  # MM-DD-YYYY only
            subject_part = content['subject_line'][:30]  # First 30 chars of subject
            campaign_name = f"{subject_part} - {date_only}"
            
            # Generate clean plain text version from HTML
            import re
            
            # Create a structured plain text version
            plain_text_parts = []
            
            # Extract key content sections
            subject = content['subject_line']
            hero_title = content['hero_title']
            greeting = content['greeting']
            main_content = content['main_content']
            cta_text = content['cta_text']
            cta_url = content['cta_url']
            urgency_text = content.get('urgency_text', '')
            offer_details = content.get('offer_details', '')
            
            # Build plain text structure
            plain_text_parts.append("View online version [weblink]")
            plain_text_parts.append("")
            plain_text_parts.append("KemisEmail")
            plain_text_parts.append("Home https://start.kemis.net\tServices https://start.kemis.net/services\tStatistics https://start.kemis.net/statistics\tContact https://start.kemis.net/contact")
            plain_text_parts.append("Join Our List https://dzvs3n3sqle.typeform.com/to/JxCYlnLb")
            plain_text_parts.append("")
            plain_text_parts.append(hero_title)
            plain_text_parts.append(greeting)
            plain_text_parts.append("")
            plain_text_parts.append(main_content)
            plain_text_parts.append("")
            plain_text_parts.append(cta_text)
            if urgency_text:
                plain_text_parts.append(urgency_text)
            if offer_details:
                plain_text_parts.append(offer_details)
            plain_text_parts.append("")
            plain_text_parts.append(cta_text)
            plain_text_parts.append(f"Link: {cta_url}")
            plain_text_parts.append("")
            plain_text_parts.append("KemisEmail – Delivering Local Deals and Offers Since 2005")
            plain_text_parts.append("")
            plain_text_parts.append("2025 © Kemis Group of Companies Inc. All rights reserved.")
            plain_text_parts.append("")
            plain_text_parts.append("Nassau West, New Providence, The Bahamas")
            plain_text_parts.append("")
            plain_text_parts.append("Sign Up https://dzvs3n3sqle.typeform.com/to/JxCYlnLb")
            plain_text_parts.append("Privacy Policy #")
            plain_text_parts.append("Terms of Use #")
            plain_text_parts.append("You are receiving this because you signed up for our Deals and Offers list.")
            plain_text_parts.append("")
            plain_text_parts.append("Click here to unsubscribe if this is no longer of interest.")
            
            plain_text = '\n'.join(plain_text_parts)
            
            # Prepare campaign data according to Sendy API documentation
            campaign_data = {
                'api_key': SENDY_API_KEY,
                'brand_id': '1',  # Your brand ID
                'from_name': 'KemisEmail',
                'from_email': 'offers@kemis.net',
                'reply_to': 'offers@kemis.net',
                'title': campaign_name,
                'subject': content['subject_line'],
                'html_text': html_template,
                'plain_text': plain_text,
                'list_ids': 'DU0p7BsJdnwE0MXNZusbMQ,fO6BdhtVFBdzyQBMcG6Yiw',  # Your list IDs
                'send_campaign': '0'  # Set to '0' for draft, '1' to send immediately
            }
            
            # Try each endpoint with different configurations
            test_configs = [
                # Standard form data
                {'data': campaign_data, 'headers': {'Content-Type': 'application/x-www-form-urlencoded'}},
                # Without content-type header (let requests set it)
                {'data': campaign_data, 'headers': {}},
                # With additional headers that might help
                {'data': campaign_data, 'headers': {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'User-Agent': 'KemisEmail/1.0',
                    'Accept': '*/*'
                }},
                # Try as JSON (some Sendy installations accept this)
                {'json': campaign_data, 'headers': {'Content-Type': 'application/json'}}
            ]
            
            for i, sendy_url in enumerate(sendy_endpoints):
                print(f"📤 Trying Sendy endpoint {i+1}/4: {sendy_url}")
                print(f"📧 Subject: {content['subject_line']}")
                print(f"📊 Template size: {len(html_template):,} bytes")
                
                for j, config in enumerate(test_configs):
                    print(f"  🔧 Config {j+1}/4: {list(config.keys())}")
                    
                    try:
                        # Send to Sendy with current config
                        response = requests.post(sendy_url, timeout=30, **config)
                        
                        print(f"  📡 Response: {response.status_code} - {response.text[:200]}...")
                        
                        if response.status_code == 200:
                            print(f"✅ SUCCESS with {sendy_url} and config {j+1}")
                            return {
                                'success': True,
                                'message': f'Successfully sent to Sendy using {sendy_url}',
                                'response': response.text
                            }
                        elif response.status_code == 403:
                            print(f"  ❌ 403 Forbidden - trying next config...")
                            continue
                        else:
                            print(f"  ❌ {response.status_code} error - trying next config...")
                            continue
                            
                    except requests.exceptions.RequestException as e:
                        print(f"  ❌ Request error: {e}")
                        continue
                
                print(f"❌ All configs failed for {sendy_url}, trying next endpoint...")
            
            # If we get here, all endpoints and configs failed
            print("❌ All Sendy endpoints and configurations failed")
            
            # Provide debugging info and curl command for manual testing
            curl_command = f"""curl -X POST https://kemis.net/sendy/api/campaigns/create.php \\
  -d "api_key={SENDY_API_KEY}" \\
  -d "brand_id=1" \\
  -d "from_name=KemisEmail" \\
  -d "from_email=offers@kemis.net" \\
  -d "reply_to=offers@kemis.net" \\
  -d "title=Test Campaign - {date_time}" \\
  -d "subject=Test Subject" \\
  -d "html_text=<b>Hello</b>" \\
  -d "plain_text=Hello" \\
  -d "list_ids=DU0p7BsJdnwE0MXNZusbMQ" \\
  -d "send_campaign=0" """
            
            return {
                'success': False,
                'error': f'Sendy API error: All endpoints returned 403 Forbidden. This suggests a server configuration issue. Try the curl command above to test manually.',
                'debug_info': {
                    'api_key': f"{SENDY_API_KEY[:8]}...",
                    'endpoints_tried': sendy_endpoints,
                    'curl_command': curl_command,
                    'suggestions': [
                        'Check if Sendy API is accessible at https://kemis.net/sendy/',
                        'Verify API key in Sendy settings',
                        'Check server .htaccess or firewall rules',
                        'Try the curl command above to test manually'
                    ]
                }
            }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Sendy API timeout - server took too long to respond'
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': 'Sendy API connection error - could not reach server'
            }
        except Exception as e:
            print(f"❌ Sendy error: {str(e)}")
            return {
                'success': False,
                'error': f'Error sending to Sendy: {str(e)}'
            }
    
    def create_html_template(self, content, image_data=None):
        """Create the full HTML email template with original formatting"""
        
        # Determine hero title color based on content
        hero_color = "#00CED1"  # Default turquoise
        if "sale" in content['hero_title'].lower() or "deal" in content['hero_title'].lower():
            hero_color = "#FF6B35"  # Orange for sales/deals
        elif "flash" in content['hero_title'].lower():
            hero_color = "#FFD700"  # Yellow for flash deals
        
        # Generate preheader text (different from subject line)
        preheader_text = content.get('preheader', '')
        if not preheader_text:
            # Create a preheader based on the main content, not subject
            preheader_text = content.get('main_content', '')[:100]  # First 100 chars of main content
            if len(preheader_text) > 100:
                preheader_text = preheader_text[:97] + "..."
        
        # Build HTML template using string concatenation to avoid CSS brace conflicts
        html_parts = []
        
        # HTML head and styles
        html_parts.append("""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html dir="ltr" lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head><meta charset="UTF-8"><meta content="width=device-width, initial-scale=1" name="viewport"><meta name="x-apple-disable-message-reformatting"><meta http-equiv="X-UA-Compatible" content="IE=edge"><meta content="telephone=no" name="format-detection">
	<title>""" + content['subject_line'] + """</title>
	<!--[if (mso 16)]><style type="text/css">     a {{text-decoration: none;}}     </style><![endif]--><!--[if gte mso 9]><style>sup {{ font-size: 100% !important; }}</style><![endif]--><!--[if gte mso 9]><noscript> <xml> <o:OfficeDocumentSettings> <o:AllowPNG></o:AllowPNG> <o:PixelsPerInch>96</o:PixelsPerInch> </o:OfficeDocumentSettings> </xml>
<![endif]--><!--[if mso]><xml> <w:WordDocument xmlns:w="urn:schemas-microsoft-com:office:word"> <w:DontUseAdvancedTypographyReadingMail/> </w:WordDocument> </xml>
<![endif]-->
	<style type="text/css">.rollover:hover .rollover-first {{ max-height:0px!important; display:none!important; }} .rollover:hover .rollover-second {{ max-height:none!important; display:block!important; }} .rollover span {{ font-size:0px; }} u + .body img ~ div div {{ display:none; }} #outlook a {{ padding:0; }} span.MsoHyperlink, span.MsoHyperlinkFollowed {{ color:inherit; mso-style-priority:99; }} a.ba {{ mso-style-priority:100!important; text-decoration:none!important; }} a[x-apple-data-detectors], #MessageViewBody a {{ color:inherit!important; text-decoration:none!important; font-size:inherit!important; font-family:inherit!important; font-weight:inherit!important; line-height:inherit!important; }} .q {{ display:none; float:left; overflow:hidden; width:0; max-height:0; line-height:0; mso-hide:all; }} @media only screen and (max-width:600px) {{.bw {{ padding-top:10px!important }} .bv {{ padding-bottom:10px!important }}
 .bu {{ padding-right:20px!important }} .bt {{ padding-left:20px!important }} .bs {{ padding-right:5px!important }} .br {{ padding-left:5px!important }} .bq {{ padding-left:0px!important }} .bp {{ padding-right:24px!important }} *[class="gmail-fix"] {{ display:none!important }} p, a {{ line-height:150%!important }} h1, h1 a {{ line-height:110%!important }} h2, h2 a {{ line-height:110%!important }} h3, h3 a {{ line-height:110%!important }} h4, h4 a {{ line-height:110%!important }} h5, h5 a {{ line-height:110%!important }} h6, h6 a {{ line-height:110%!important }} .o td a {{ font-size:12px!important }} .bm p, .bm a {{ font-size:14px!important }}
 .bl p, .bl a {{ font-size:14px!important }} .bk p, .bk a {{ font-size:12px!important }} .bh, .bh h1, .bh h2, .bh h3, .bh h4, .bh h5, .bh h6 {{ text-align:center!important }} .bg .rollover:hover .rollover-second, .bh .rollover:hover .rollover-second, .bi .rollover:hover .rollover-second {{ display:inline!important }} a.ba, button.ba {{ font-size:20px!important; padding:10px 20px 10px 20px!important; line-height:120%!important }} a.ba, button.ba, .be {{ display:inline-block!important }} .z, .z .ba, .bb, .bb td, .o {{ display:inline-block!important }} .t table, .u table, .v table, .t, .v, .u {{ width:100%!important; max-width:600px!important }} .adapt-img {{ width:100%!important; height:auto!important }} .q {{ width:auto!important; overflow:visible!important; float:none!important; max-height:inherit!important; line-height:inherit!important }} tr.q {{ display:table-row!important }} .o td {{ width:1%!important }}
 table.n, .esd-block-html table {{ width:auto!important }} .h-auto {{ height:auto!important }} .l .m.e, .l .m.e * {{ font-size:13px!important; line-height:150%!important }} .k .d.e, .k .d.e * {{ font-size:16px!important; line-height:150%!important }} .j .i, .j .i * {{ font-size:48px!important; line-height:110%!important }} .h .i, .j .i * {{ font-size:48px!important; line-height:110%!important }} .f .g.e, .f .g.e * {{ font-size:22px!important; line-height:150%!important }} .c .d.e, .c .d.e * {{ font-size:16px!important; line-height:150%!important }} .a .b, .a .b * {{ font-size:14px!important; line-height:150%!important }} }} @media screen and (max-width:384px) {{.mail-message-content {{ width:414px!important }} }}
	</style>
</head>
<body class="body" style="width:100%;height:100%;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;padding:0;Margin:0">
<p><span style="display:none !important;color:#ffffff;height:0;mso-hide:all;line-height:0;visibility:hidden;opacity:0;font-size:0px;width:0">""" + preheader_text + """</span></p>""")
        
        # Main email structure
        html_parts.append("""<!--[if gte mso 9]><v:background xmlns:v="urn:schemas-microsoft-com:vml" fill="t"> <v:fill type="tile" color="#fafafa"></v:fill> </v:background><![endif]-->

<table cellpadding="0" cellspacing="0" class="es-wrapper" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;padding:0;Margin:0;width:100%;height:100%;background-repeat:repeat;background-position:center top;background-color:#FAFAFA" width="100%">
	<tbody>
		<tr>
			<td style="padding:0;Margin:0" valign="top">
			<table align="center" cellpadding="0" cellspacing="0" class="t" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;width:100%;table-layout:fixed !important">
				<tbody>
					<tr>
						<td align="center" class="es-info-area" style="padding:0;Margin:0">
						<table align="center" bgcolor="#00000000" cellpadding="0" cellspacing="0" class="bm" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;background-color:transparent;width:600px">
							<tbody>
								<tr>
									<td align="left" style="padding:20px;Margin:0">
									<table cellpadding="0" cellspacing="0" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
										<tbody>
											<tr>
												<td align="center" style="padding:0;Margin:0;width:560px" valign="top">
												<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
													<tbody>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0">
															<p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:18px;letter-spacing:0;color:#CCCCCC;font-size:12px"><a href="[webversion]" style="mso-line-height-rule:exactly;text-decoration:underline;color:#CCCCCC;font-size:12px" target="_blank">View online version</a></p>
															</td>
														</tr>
													</tbody>
												</table>
												</td>
											</tr>
										</tbody>
									</table>
									</td>
								</tr>
							</tbody>
						</table>
						</td>
					</tr>
				</tbody>
			</table>

			<!-- NEW KEMISEMAIL HEADER WITH MENU -->
			<table align="center" cellpadding="0" cellspacing="0" class="t" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;width:100%;table-layout:fixed !important">
				<tbody>
					<tr>
						<td align="center" style="padding:0;Margin:0">
						<table align="center" bgcolor="#ffffff" cellpadding="0" cellspacing="0" class="bm" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;background-color:#ffffff;width:600px">
							<tbody>
								<tr>
									<td align="center" style="Margin:0;padding-top:25px;padding-right:20px;padding-bottom:25px;padding-left:20px">
									<table cellpadding="0" cellspacing="0" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
										<tbody>
											<tr>
												<td align="center" style="padding:0;Margin:0;width:560px" valign="top">
												<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
													<tbody>
														<tr>
															<td align="left" style="padding:0;Margin:0;width:200px;vertical-align:middle">
															<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
																<tbody>
																	<tr>
																		<td align="left" style="padding:0;Margin:0;width:30px;vertical-align:middle">
																		<!-- Email Icon -->
																		<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="display:block;">
																			<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" stroke="#00CED1" stroke-width="2" fill="none"/>
																			<polyline points="4,6 12,13 20,6" stroke="#00CED1" stroke-width="2" fill="none"/>
																		</svg>
																		</td>
																		<td align="left" style="padding:0;Margin:0;padding-left:5px;vertical-align:middle">
																		<a href="https://start.kemis.net" style="text-decoration:none;color:#00CED1;">
																		<h2 style="Margin:0;font-family:arial, 'helvetica neue', helvetica, sans-serif;mso-line-height-rule:exactly;letter-spacing:0;font-size:18px;font-style:normal;font-weight:bold;line-height:22px;color:#00CED1">KemisEmail</h2>
																		</a>
																		</td>
																	</tr>
																</tbody>
															</table>
															</td>
															<td align="center" style="padding:0;Margin:0;width:200px;vertical-align:middle">
															<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
																<tbody>
																	<tr>
																		<td align="center" style="padding:0;Margin:0;padding-right:15px">
																		<a href="https://kemis.net" style="text-decoration:none;color:#666666;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-size:14px;font-weight:normal;">Home</a>
																		</td>
																		<td align="center" style="padding:0;Margin:0;padding-right:15px">
																		<a href="https://start.kemis.net/services" style="text-decoration:none;color:#666666;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-size:14px;font-weight:normal;">Services</a>
																		</td>
																		<td align="center" style="padding:0;Margin:0;padding-right:15px">
																		<a href="https://start.kemis.net/statistics" style="text-decoration:none;color:#666666;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-size:14px;font-weight:normal;">Statistics</a>
																		</td>
																		<td align="center" style="padding:0;Margin:0">
																		<a href="https://start.kemis.net/contact" style="text-decoration:none;color:#666666;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-size:14px;font-weight:normal;">Contact</a>
																		</td>
																	</tr>
																</tbody>
															</table>
															</td>
															<td align="right" style="padding:0;Margin:0;width:160px;vertical-align:middle">
															<a href="https://dzvs3n3sqle.typeform.com/to/JxCYlnLb" style="display:inline-block;background-color:#00CED1;color:#ffffff;text-decoration:none;padding:8px 16px;border-radius:4px;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-size:14px;font-weight:bold;line-height:1.2;text-align:center;margin:0;">Join Our List</a>
															</td>
														</tr>
													</tbody>
												</table>
												</td>
											</tr>
										</tbody>
									</table>
									</td>
								</tr>
							</tbody>
						</table>""")
        
        # Hero section
        html_parts.append("""<!-- HERO SECTION -->
			<table align="center" cellpadding="0" cellspacing="0" class="t" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;width:100%;table-layout:fixed !important">
				<tbody>
					<tr>
						<td align="center" style="padding:0;Margin:0">
						<table align="center" bgcolor="#ffffff" cellpadding="0" cellspacing="0" class="bm" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;background-color:#ffffff;width:600px">
							<tbody>
								<tr>
									<td align="center" style="Margin:0;padding-top:0px;padding-right:20px;padding-bottom:0px;padding-left:20px">
									<table cellpadding="0" cellspacing="0" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
										<tbody>
											<tr>
												<td align="center" style="padding:0;Margin:0;width:560px" valign="top">
												<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
													<tbody>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0">
															<h1 style="Margin:0;font-family:arial, 'helvetica neue', helvetica, sans-serif;mso-line-height-rule:exactly;letter-spacing:0;font-size:32px;font-style:normal;font-weight:bold;line-height:38px;color:""" + hero_color + """>""" + content['hero_title'] + """</h1>
															</td>
														</tr>
													</tbody>
												</table>
												</td>
											</tr>
										</tbody>
									</table>
									</td>
								</tr>
							</tbody>
						</table>
						</td>
					</tr>
				</tbody>
			</table>""")
        
        # Image section (if provided)
        if image_data:
            image_html = self._get_image_html(image_data, content['hero_title'], content.get('cta_url'))
            html_parts.append("""<!-- IMAGE SECTION -->
			<table align="center" cellpadding="0" cellspacing="0" class="t" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;width:100%;table-layout:fixed !important">
				<tbody>
					<tr>
						<td align="center" style="padding:0;Margin:0">
						<table align="center" bgcolor="#ffffff" cellpadding="0" cellspacing="0" class="bm" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;background-color:#ffffff;width:600px">
							<tbody>
								<tr>
									<td align="center" style="Margin:0;padding-top:20px;padding-right:20px;padding-bottom:20px;padding-left:20px">
									<table cellpadding="0" cellspacing="0" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
										<tbody>
											<tr>
												<td align="center" style="padding:0;Margin:0;width:560px" valign="top">
												<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
													<tbody>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0">
															""" + image_html + """
															</td>
														</tr>
													</tbody>
												</table>
												</td>
											</tr>
										</tbody>
									</table>
									</td>
								</tr>
							</tbody>
						</table>
						</td>
					</tr>
				</tbody>
			</table>""")
        
        # Content section
        html_parts.append("""<!-- CONTENT SECTION -->
			<table align="center" cellpadding="0" cellspacing="0" class="t" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;width:100%;table-layout:fixed !important">
				<tbody>
					<tr>
						<td align="center" style="padding:0;Margin:0">
						<table align="center" bgcolor="#ffffff" cellpadding="0" cellspacing="0" class="bm" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;background-color:#ffffff;width:600px">
							<tbody>
								<tr>
									<td align="center" style="Margin:0;padding-top:20px;padding-right:20px;padding-bottom:20px;padding-left:20px">
									<table cellpadding="0" cellspacing="0" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
										<tbody>
											<tr>
												<td align="center" style="padding:0;Margin:0;width:560px" valign="top">
												<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
													<tbody>
														<tr>
															<td align="left" class="bk" style="padding:0;Margin:0">
															<p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:24px;letter-spacing:0;font-size:16px;font-style:normal;font-weight:normal;color:#666666">""" + content['greeting'] + """</p>
															</td>
														</tr>
														<tr>
															<td align="left" class="bk" style="padding:0;Margin:0;padding-top:20px">
															<p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:24px;letter-spacing:0;font-size:16px;font-style:normal;font-weight:normal;color:#666666">""" + content['main_content'] + """</p>
															</td>
														</tr>""")
        
        # Add urgency text if present
        if content.get('urgency_text'):
            html_parts.append("""														<tr>
															<td align="left" class="bk" style="padding:0;Margin:0;padding-top:20px">
															<p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:24px;letter-spacing:0;font-size:16px;font-style:normal;font-weight:bold;color:#FF6B35">""" + content['urgency_text'] + """</p>
															</td>
														</tr>""")
        
        # Add offer details if present
        if content.get('offer_details'):
            html_parts.append("""														<tr>
															<td align="left" class="bk" style="padding:0;Margin:0;padding-top:20px">
															<p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:24px;letter-spacing:0;font-size:16px;font-style:normal;font-weight:normal;color:#666666">""" + content['offer_details'] + """</p>
															</td>
														</tr>""")
        
        # CTA section
        html_parts.append("""													</tbody>
												</table>
												</td>
											</tr>
										</tbody>
									</table>
									</td>
								</tr>
							</tbody>
						</table>
						</td>
					</tr>
				</tbody>
			</table>

			<!-- CTA SECTION -->
			<table align="center" cellpadding="0" cellspacing="0" class="t" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;width:100%;table-layout:fixed !important">
				<tbody>
					<tr>
						<td align="center" style="padding:0;Margin:0">
						<table align="center" bgcolor="#ffffff" cellpadding="0" cellspacing="0" class="bm" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;background-color:#ffffff;width:600px">
							<tbody>
								<tr>
									<td align="center" style="Margin:0;padding-top:20px;padding-right:20px;padding-bottom:20px;padding-left:20px">
									<table cellpadding="0" cellspacing="0" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
										<tbody>
											<tr>
												<td align="center" style="padding:0;Margin:0;width:560px" valign="top">
												<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
													<tbody>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0">
															<h2 style="Margin:0;font-family:arial, 'helvetica neue', helvetica, sans-serif;mso-line-height-rule:exactly;letter-spacing:0;font-size:24px;font-style:normal;font-weight:bold;line-height:28px;color:#00CED1">🎯 Ready to Take Action?</h2>
															</td>
														</tr>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0;padding-top:20px">
															<a href="""" + content.get('cta_url', '#') + """" style="display:inline-block;background-color:#00CED1;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-size:16px;font-weight:bold;line-height:1.2;text-align:center;margin:0;">""" + content['cta_text'] + """</a>
															</td>
														</tr>
													</tbody>
												</table>
												</td>
											</tr>
										</tbody>
									</table>
									</td>
								</tr>
							</tbody>
						</table>
						</td>
					</tr>
				</tbody>
			</table>""")
        
        # Footer
        html_parts.append("""<!-- FOOTER -->
			<table align="center" cellpadding="0" cellspacing="0" class="t" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;width:100%;table-layout:fixed !important">
				<tbody>
					<tr>
						<td align="center" style="padding:0;Margin:0">
						<table align="center" bgcolor="#f8f9fa" cellpadding="0" cellspacing="0" class="bm" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;background-color:#f8f9fa;width:600px">
							<tbody>
								<tr>
									<td align="center" style="Margin:0;padding-top:30px;padding-right:20px;padding-bottom:30px;padding-left:20px">
									<table cellpadding="0" cellspacing="0" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
										<tbody>
											<tr>
												<td align="center" style="padding:0;Margin:0;width:560px" valign="top">
												<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
													<tbody>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0">
															<h3 style="Margin:0;font-family:arial, 'helvetica neue', helvetica, sans-serif;mso-line-height-rule:exactly;letter-spacing:0;font-size:18px;font-style:normal;font-weight:bold;line-height:22px;color:#00CED1">KemisEmail – Delivering Local Deals and Offers Since 2005</h3>
															</td>
														</tr>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0;padding-top:20px">
															<p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:18px;letter-spacing:0;font-size:12px;font-style:normal;font-weight:normal;color:#666666">2025 © Kemis Group of Companies Inc. All rights reserved.</p>
															</td>
														</tr>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0;padding-top:10px">
															<p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:18px;letter-spacing:0;font-size:12px;font-style:normal;font-weight:normal;color:#666666">Nassau West, New Providence, The Bahamas</p>
															</td>
														</tr>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0;padding-top:20px">
															<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
																<tbody>
																	<tr>
																		<td align="center" style="padding:0;Margin:0;padding-right:15px">
																		<a href="https://dzvs3n3sqle.typeform.com/to/JxCYlnLb" style="text-decoration:none;color:#00CED1;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-size:14px;font-weight:normal;">Sign Up</a>
																		</td>
																		<td align="center" style="padding:0;Margin:0;padding-right:15px">
																		<a href="#" style="text-decoration:none;color:#666666;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-size:14px;font-weight:normal;">Privacy Policy</a>
																		</td>
																		<td align="center" style="padding:0;Margin:0">
																		<a href="#" style="text-decoration:none;color:#666666;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-size:14px;font-weight:normal;">Terms of Use</a>
																		</td>
																	</tr>
																</tbody>
															</table>
															</td>
														</tr>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0;padding-top:20px">
															<p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:18px;letter-spacing:0;font-size:12px;font-style:normal;font-weight:normal;color:#666666">You are receiving this because you signed up for our Deals and Offers list.</p>
															</td>
														</tr>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0;padding-top:10px">
															<p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:18px;letter-spacing:0;font-size:12px;font-style:normal;font-weight:normal;color:#666666">Click here to unsubscribe if this is no longer of interest.</p>
															</td>
														</tr>
													</tbody>
												</table>
												</td>
											</tr>
										</tbody>
									</table>
									</td>
								</tr>
							</tbody>
						</table>
						</td>
					</tr>
				</tbody>
			</table>
		</td>
	</tr>
</tbody>
</table>
</body>
</html>""")
        
        # Join all parts
        html_template = ''.join(html_parts)
        
        return html_template
    
    def _get_image_html(self, image_data, alt_text, cta_url=None):
        """Generate the image HTML with proper styling and optional CTA link"""
        if image_data:
            if cta_url:
                return f'<a href="{cta_url}" target="_blank" style="text-decoration: none;"><img alt="{alt_text}" class="adapt-img" src="{image_data}" style="display: block; font-size: 14px; border: 0px; outline: none; text-decoration: none; border-radius: 15px; width: 560px; height: auto;" title="{alt_text}" /></a>'
            else:
                return f'<img alt="{alt_text}" class="adapt-img" src="{image_data}" style="display: block; font-size: 14px; border: 0px; outline: none; text-decoration: none; border-radius: 15px; width: 560px; height: auto;" title="{alt_text}" />'
        else:
            if cta_url:
                return f'<a href="{cta_url}" target="_blank" style="text-decoration: none;"><div style="display: block; font-size: 14px; border: 0px; outline: none; text-decoration: none; border-radius: 15px; width: 560px; height: 400px; background: linear-gradient(135deg, #00CED1 0%, #FFD700 100%); display: flex; align-items: center; justify-content: center; color: white; font-size: 24px; font-weight: bold;">{alt_text}</div></a>'
            else:
                return f'<div style="display: block; font-size: 14px; border: 0px; outline: none; text-decoration: none; border-radius: 15px; width: 560px; height: 400px; background: linear-gradient(135deg, #00CED1 0%, #FFD700 100%); display: flex; align-items: center; justify-content: center; color: white; font-size: 24px; font-weight: bold;">{alt_text}</div>'

# Initialize the generator
generator = TemplateGenerator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_template():
    try:
        # Handle form data instead of JSON
        prompt = request.form.get('prompt', '')
        image_option = request.form.get('imageOption', 'ai')
        custom_cta_link = request.form.get('ctaLink', '')
        generate_preheader = request.form.get('generatePreheader', 'yes') == 'yes'
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        # Generate content
        content = generator.generate_email_content(prompt)
        
        # Override CTA URL if custom link provided
        if custom_cta_link:
            content['cta_url'] = custom_cta_link
            print(f"🔗 Using custom CTA link: {custom_cta_link}")
        
        # Handle preheader generation
        if not generate_preheader:
            content['preheader'] = ''  # Empty preheader
            print(f"📝 Preheader disabled for this campaign")
        else:
            print(f"📝 Preheader enabled for this campaign")
        
        # Handle image based on option
        image_data = None
        image_prompt = None
        image_source = "AI Generated"
        
        if image_option == 'ai':
            # Generate image prompt and image
            image_prompt = generator.generate_image_prompt(content)
            image_data = generator.generate_image(image_prompt)
            image_source = "AI Generated"
        elif image_option == 'upload':
            # Use uploaded image
            if 'uploadedImage' in request.form:
                image_data = request.form['uploadedImage']
                image_source = "Uploaded"
            else:
                return jsonify({'error': 'No image uploaded'}), 400
        elif image_option == 'none':
            # No image
            image_source = "None"
        
        # Create HTML template
        html_template = generator.create_html_template(content, image_data)
        
        # Create campaign name from subject line
        import re
        campaign_name = re.sub(r'[^a-zA-Z0-9\s-]', '', content['subject_line'])
        campaign_name = re.sub(r'\s+', '-', campaign_name.strip())
        campaign_name = campaign_name[:50]  # Limit length
        
        # Save template to templates folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        template_filename = f"templates/{campaign_name}_{timestamp}.html"
        
        # Ensure templates directory exists
        import os
        os.makedirs('templates', exist_ok=True)
        
        with open(template_filename, 'w', encoding='utf-8') as f:
            f.write(html_template)
        
        # Save image to images folder if it's base64 data
        if image_data and image_data.startswith('data:image'):
            import base64
            try:
                # Extract image data from base64
                image_format = image_data.split(';')[0].split('/')[1]
                image_data_clean = image_data.split(',')[1]
                image_bytes = base64.b64decode(image_data_clean)
                
                # Save to images folder
                os.makedirs('images', exist_ok=True)
                image_filename = f"images/{campaign_name}_{timestamp}.{image_format}"
                
                with open(image_filename, 'wb') as f:
                    f.write(image_bytes)
                
                print(f"💾 Saved image: {image_filename}")
            except Exception as e:
                print(f"⚠️ Could not save image: {e}")
        
        filename = template_filename
        
        # Check template size before returning
        html_size = len(html_template.encode('utf-8'))
        print(f"📧 Generated template size: {html_size:,} bytes")
        
        # If template is too large, try to compress it
        if html_size > 800 * 1024:  # 800KB limit for response
            print(f"⚠️ Large template detected: {html_size:,} bytes, compressing...")
            
            # Try to compress by removing large base64 images
            import re
            base64_pattern = r'data:image/[^;]+;base64,[A-Za-z0-9+/=]{1000,}'
            compressed_html = re.sub(base64_pattern, 'data:image/jpeg;base64,PLACEHOLDER_IMAGE_REMOVED', html_template)
            
            compressed_size = len(compressed_html.encode('utf-8'))
            print(f"📧 Compressed template size: {compressed_size:,} bytes")
            
            if compressed_size > 800 * 1024:
                print(f"❌ Template still too large: {compressed_size:,} bytes")
                return jsonify({
                    'success': False,
                    'error': 'Generated template is too large. Please try with a shorter prompt or no image.',
                    'template_size': html_size,
                    'compressed_size': compressed_size
                }), 413
            else:
                html_template = compressed_html
                print(f"✅ Template compressed successfully")
        
        # Check if image data is too large (limit to 500KB for response)
        if image_data and len(image_data.encode('utf-8')) > 500 * 1024:
            print("⚠️ Image data too large for response, removing...")
            image_data = None
            image_source = "Removed (too large for response)"
        
        return jsonify({
            'success': True,
            'content': content,
            'image_prompt': image_prompt,
            'image_data': image_data,
            'image_source': image_source,
            'html_template': html_template,
            'filename': filename,
            'template_size': len(html_template.encode('utf-8'))
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_template(filename):
    try:
        # Check if file exists in templates folder
        template_path = f"templates/{filename}"
        if os.path.exists(template_path):
            return send_file(template_path, as_attachment=True)
        else:
            return jsonify({'error': 'Template file not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/send-to-sendy', methods=['POST'])
def send_to_sendy():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Extract data from request
        content = data.get('content', {})
        html_template = data.get('html_template', '')
        filename = data.get('filename', '')
        
        if not content or not html_template:
            return jsonify({'error': 'Missing content or HTML template'}), 400
        
        # Check if HTML template is too large (over 1MB)
        html_size = len(html_template.encode('utf-8'))
        if html_size > 1024 * 1024:  # 1MB
            print(f"📧 Large HTML template detected: {html_size:,} bytes")
            
            # Try to compress by removing large base64 images
            import re
            # Find and replace large base64 images with placeholder
            base64_pattern = r'data:image/[^;]+;base64,[A-Za-z0-9+/=]{1000,}'
            compressed_html = re.sub(base64_pattern, 'data:image/jpeg;base64,PLACEHOLDER_IMAGE_REMOVED', html_template)
            
            if len(compressed_html.encode('utf-8')) > 1024 * 1024:
                return jsonify({
                    'success': False,
                    'error': 'Template too large even after compression. Please use smaller images or no images.'
                }), 413
            
            print(f"✅ HTML template compressed from {html_size:,} to {len(compressed_html.encode('utf-8')):,} bytes")
            html_template = compressed_html
        
        # Send to Sendy
        result = generator.send_to_sendy(content, html_template, filename)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 