import os
import json
import re
import requests
from datetime import datetime
import openai
from flask import Flask, render_template, request, jsonify, send_file
import base64
from PIL import Image
import io
import uuid
from dotenv import load_dotenv

# Try to import boto3 for S3 uploads (optional)
try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    print("⚠️ boto3 not available - S3 uploads will be disabled. Install with: pip install boto3")

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'your-openai-key-here')
DALLE_API_KEY = os.getenv('DALLE_API_KEY', 'your-dalle-key-here')
SENDY_API_KEY = os.getenv('SENDY_API_KEY', '')

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
AWS_S3_BUCKET = os.getenv('AWS_S3_BUCKET', '')
AWS_S3_REGION = os.getenv('AWS_S3_REGION', 'us-east-1')
AWS_S3_BASE_URL = os.getenv('AWS_S3_BASE_URL', '')

# Check if S3 is configured
S3_CONFIGURED = (
    BOTO3_AVAILABLE and
    AWS_ACCESS_KEY_ID and
    AWS_SECRET_ACCESS_KEY and
    AWS_S3_BUCKET
)

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
        if not OPENAI_API_KEY or OPENAI_API_KEY == 'your-openai-key-here':
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
    def generate_email_content(self, prompt):
        """Generate email content using OpenAI"""
        system_prompt = """You are a professional email marketing expert. Create SHORT, CLEAN email content that:
        - Uses professional, engaging marketing language
        - Uses clear, friendly greetings like "Hi" or "Hello"
        - Is structured with headlines, subheadlines, and bullet points for clarity
        - Use single space after periods, no double spacing
        - Include 2-3 relevant emojis maximum
        - Focus on the specific business/promotion mentioned
        - Has a clear call-to-action
        - No long paragraphs or run-on sentences
        
        Return the content in JSON format with these fields:
        {
            "subject_line": "Email subject line",
            "hero_title": "Main headline (max 3 words)",
            "greeting": "Personal greeting with [Name,fallback=there]",
            "headline": "Main value proposition headline (compelling benefit)",
            "subheadline": "Supporting subheadline that expands on the value",
            "bullet_points": ["Key benefit 1", "Key benefit 2", "Key benefit 3"],
            "main_content": "Closing paragraph - 2-3 short lines maximum, separated by &nbsp;",
            "cta_text": "Call to action button text",
            "cta_url": "Call to action URL",
            "urgency_text": "Urgency message if applicable",
            "offer_details": "Unique action-focused summary for CTA box (e.g., 'Click below to claim your 20% discount before Friday!') - must be different from main_content"
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
            "greeting": "Hi [Name,fallback=there]! 🎉",
            "headline": "Exclusive Deal Just For You",
            "subheadline": "Limited Time Opportunity",
            "bullet_points": ["Great value", "Quality service", "Special pricing"],
            "main_content": f"Check out this amazing deal! {prompt}",
            "cta_text": "LEARN MORE",
            "cta_url": "https://www.kemis.net",
            "urgency_text": "Limited time offer!",
            "offer_details": "Act now to secure your discount before this offer expires!"
        }
    
    def send_to_sendy(self, content, html_template, filename, list_ids=None, send_option='draft', scheduled_datetime=None):
        """Send template to Sendy API
        
        Args:
            content: Email content dictionary
            html_template: HTML template string
            filename: Template filename
            list_ids: Comma-separated list IDs (defaults to hardcoded lists)
            send_option: 'draft', 'send_now', or 'schedule'
            scheduled_datetime: Unix timestamp for scheduled send (required if send_option='schedule')
        """
        if not SENDY_API_KEY:
            return {
                'success': False,
                'error': 'SENDY_API_KEY environment variable is not set'
            }
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
            
            # Use provided list_ids or default to hardcoded ones
            if not list_ids:
                list_ids = 'DU0p7BsJdnwE0MXNZusbMQ,fO6BdhtVFBdzyQBMcG6Yiw'
            
            # Determine send_campaign value and schedule_date_time based on send_option
            schedule_date_time_str = None
            if send_option == 'send_now':
                send_campaign_value = '1'
            elif send_option == 'schedule' and scheduled_datetime:
                # Convert Unix timestamp to datetime object
                schedule_dt = datetime.fromtimestamp(int(scheduled_datetime))
                
                # Round minutes to nearest 5-minute increment (Sendy requirement)
                minutes = schedule_dt.minute
                rounded_minutes = round(minutes / 5) * 5
                if rounded_minutes == 60:
                    rounded_minutes = 0
                    schedule_dt = schedule_dt.replace(hour=schedule_dt.hour + 1, minute=0)
                else:
                    schedule_dt = schedule_dt.replace(minute=rounded_minutes)
                
                # Format as "Month Day, Year h:mmam/pm" (e.g., "June 15, 2021 6:05pm")
                # Use %-d on Linux/Mac or %#d on Windows to remove leading zero, but for compatibility use manual replacement
                schedule_date_time_str = schedule_dt.strftime("%B %d, %Y %I:%M%p").lower()
                # Remove leading zero from day if present (e.g., "June 05, 2021" -> "June 5, 2021")
                schedule_date_time_str = re.sub(r'(\w+)\s+0(\d),', r'\1 \2,', schedule_date_time_str)
                # Remove leading zero from hour if present (e.g., "06:05pm" -> "6:05pm")
                schedule_date_time_str = re.sub(r'(\s)0(\d:\d{2}[ap]m)', r'\1\2', schedule_date_time_str)
                
                # Set send_campaign to '1' for scheduled campaigns (Sendy requirement: send_campaign=1 + schedule_date_time = scheduled send)
                send_campaign_value = '1'
            else:
                send_campaign_value = '0'  # Draft
            
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
                'list_ids': list_ids,
                'send_campaign': send_campaign_value
            }
            
            # Add schedule_date_time parameter if scheduling
            if schedule_date_time_str:
                campaign_data['schedule_date_time'] = schedule_date_time_str
            
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
  -d "title=Test Campaign - {now.strftime('%m-%d-%Y %H:%M')}" \\
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
    
    def create_html_template(self, content, images=None):
        """Create the full HTML email template with original formatting"""
        
        # Ensure images is a list
        if images is None:
            images = []
        elif not isinstance(images, list):
            images = [images]
        
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
        
        html_template = f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html dir="ltr" lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head><meta charset="UTF-8"><meta content="width=device-width, initial-scale=1" name="viewport"><meta name="x-apple-disable-message-reformatting"><meta http-equiv="X-UA-Compatible" content="IE=edge"><meta content="telephone=no" name="format-detection"><meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">
	<title>{content['subject_line']}</title>
	<!--[if (mso 16)]><style type="text/css">     a {{text-decoration: none;}}     </style><![endif]--><!--[if gte mso 9]><style>sup {{ font-size: 100% !important; }}</style><![endif]--><!--[if gte mso 9]><noscript> <xml> <o:OfficeDocumentSettings> <o:AllowPNG></o:AllowPNG> <o:PixelsPerInch>96</o:PixelsPerInch> </o:OfficeDocumentSettings> </xml>
<![endif]--><!--[if mso]><xml> <w:WordDocument xmlns:w="urn:schemas-microsoft-com:office:word"> <w:DontUseAdvancedTypographyReadingMail/> </w:WordDocument> </xml>
<![endif]-->
	<style type="text/css">.rollover:hover .rollover-first {{ max-height:0px!important; display:none!important; }} .rollover:hover .rollover-second {{ max-height:none!important; display:block!important; }} .rollover span {{ font-size:0px; }} u + .body img ~ div div {{ display:none; }} #outlook a {{ padding:0; }} span.MsoHyperlink, span.MsoHyperlinkFollowed {{ color:inherit; mso-style-priority:99; }} a.ba {{ mso-style-priority:100!important; text-decoration:none!important; }} a[x-apple-data-detectors], #MessageViewBody a {{ color:inherit!important; text-decoration:none!important; font-size:inherit!important; font-family:inherit!important; font-weight:inherit!important; line-height:inherit!important; }} .q {{ display:none; float:left; overflow:hidden; width:0; max-height:0; line-height:0; mso-hide:all; }} @media only screen and (max-width:600px) {{.bw {{ padding-top:10px!important }} .bv {{ padding-bottom:10px!important }}
 .bu {{ padding-right:20px!important }} .bt {{ padding-left:20px!important }} .bs {{ padding-right:5px!important }} .br {{ padding-left:5px!important }} .bq {{ padding-left:0px!important }} .bp {{ padding-right:24px!important }} *[class="gmail-fix"] {{ display:none!important }} p, a {{ line-height:150%!important }} h1, h1 a {{ line-height:110%!important }} h2, h2 a {{ line-height:110%!important }} h3, h3 a {{ line-height:110%!important }} h4, h4 a {{ line-height:110%!important }} h5, h5 a {{ line-height:110%!important }} h6, h6 a {{ line-height:110%!important }} .bm p {{ }} .bl p {{ }} .bk p {{ }} h1 {{ font-size:36px!important; text-align:left }} h2 {{ font-size:26px!important; text-align:left }} h3 {{ font-size:20px!important; text-align:left }} h4 {{ font-size:24px!important; text-align:left }} h5 {{ font-size:20px!important; text-align:left }} h6 {{ font-size:16px!important; text-align:left }} .o td a {{ font-size:12px!important }} .bm p, .bm a {{ font-size:14px!important }}
 .bl p, .bl a {{ font-size:14px!important }} .bk p, .bk a {{ font-size:12px!important }} .bh, .bh h1, .bh h2, .bh h3, .bh h4, .bh h5, .bh h6 {{ text-align:center!important }} .bg .rollover:hover .rollover-second, .bh .rollover:hover .rollover-second, .bi .rollover:hover .rollover-second {{ display:inline!important }} a.ba, button.ba {{ font-size:20px!important; padding:10px 20px 10px 20px!important; line-height:120%!important }} a.ba, button.ba, .be {{ display:inline-block!important }} .z, .z .ba, .bb, .bb td, .o {{ display:inline-block!important }} .t table, .u table, .v table, .t, .v, .u {{ width:100%!important; max-width:600px!important }} .adapt-img {{ width:100%!important; height:auto!important }} .q {{ width:auto!important; overflow:visible!important; float:none!important; max-height:inherit!important; line-height:inherit!important }} tr.q {{ display:table-row!important }} .o td {{ width:1%!important }}
 table.n, .esd-block-html table {{ width:auto!important }} .h-auto {{ height:auto!important }} .l .m.e, .l .m.e * {{ font-size:13px!important; line-height:150%!important }} .k .d.e, .k .d.e * {{ font-size:16px!important; line-height:150%!important }} .j .i, .j .i * {{ font-size:48px!important; line-height:110%!important }} .h .i, .j .i * {{ font-size:48px!important; line-height:110%!important }} .f .g.e, .f .g.e * {{ font-size:22px!important; line-height:150%!important }} .c .d.e, .c .d.e * {{ font-size:16px!important; line-height:150%!important }} .a .b, .a .b * {{ font-size:14px!important; line-height:150%!important }} .header-logo, .header-menu, .header-cta {{ display:block!important; width:100%!important; text-align:center!important; padding:10px 0!important }} .header-menu td {{ display:block!important; padding:8px 0!important; text-align:center!important }} .footer-links td {{ display:block!important; text-align:center!important; padding:5px 0!important }} }} @media screen and (max-width:384px) {{.mail-message-content {{ width:414px!important }} }} @media (prefers-color-scheme: dark) {{ body, .es-wrapper {{ background-color:#1a1a1a!important }} .bm {{ background-color:#2d2d2d!important }} p, h1, h2, h3, h4, h5, h6, td, li {{ color:#ffffff!important }} a {{ color:#00CED1!important }} .footer-bg {{ background-color:#1a1a1a!important }} }}
	</style>
</head>
<body class="body" style="width:100%;height:100%;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;padding:0;Margin:0">
<p><span style="display:none !important;color:#ffffff;height:0;mso-hide:all;line-height:0;visibility:hidden;opacity:0;font-size:0px;width:0">{preheader_text}</span></p>
<!--[if gte mso 9]><v:background xmlns:v="urn:schemas-microsoft-com:vml" fill="t"> <v:fill type="tile" color="#fafafa"></v:fill> </v:background><![endif]-->

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
															<td align="left" class="header-logo" style="padding:0;Margin:0;width:200px;vertical-align:middle">
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
															<td align="center" class="header-menu" style="padding:0;Margin:0;width:200px;vertical-align:middle">
															<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
																<tbody>
																	<tr>
																		<td align="center" style="padding:0;Margin:0">
																		<a href="https://start.kemis.net/services" style="text-decoration:none;color:#666666;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-size:14px;font-weight:normal;">Advertising Rates</a>
																		</td>
																	</tr>
																</tbody>
															</table>
															</td>
															<td align="right" class="header-cta" style="padding:0;Margin:0;width:160px;vertical-align:middle">
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
						</table>
						</td>
					</tr>
				</tbody>
			</table>

			<!-- MAIN CONTENT SECTION -->
			<table align="center" cellpadding="0" cellspacing="0" class="t" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;width:100%;table-layout:fixed !important">
				<tbody>
					<tr>
						<td align="center" style="padding:0;Margin:0">
						<table align="center" bgcolor="#ffffff" cellpadding="0" cellspacing="0" class="bm" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;background-color:#FFFFFF;width:600px">
							<tbody>
								<tr>
									<td align="left" style="Margin:0;padding-top:20px;padding-right:20px;padding-bottom:10px;padding-left:20px">
									<table cellpadding="0" cellspacing="0" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
										<tbody>
											<tr>
												<td align="center" style="padding:0;Margin:0;width:560px" valign="top">
												<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
													<tbody>
														<tr>
															<td align="center" style="padding:0;Margin:0;font-size:0px">
																{self._get_images_html(images, content['subject_line'], content['cta_url'])}
															</td>
														</tr>
														<tr class="r">
															<td align="center" class="j" style="Margin:0;padding-top:15px;padding-right:35px;padding-bottom:15px;padding-left:35px">
															<h1 class="bh i e" style="Margin:0;font-family:arial, 'helvetica neue', helvetica, sans-serif;mso-line-height-rule:exactly;letter-spacing:0;font-size:72px;font-style:normal;font-weight:bold;line-height:64.8px;color:{hero_color}">{content['hero_title']}</h1>
															</td>
														</tr>
														<tr>
															<td align="left" class="c bt bu" style="Margin:0;padding-top:3px;padding-bottom:3px;padding-right:30px;padding-left:30px">
															<p class="d e" style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:27px;letter-spacing:0;color:#333333;font-size:18px;text-align:center">{content.get('greeting', 'Hi [Name,fallback=there]!')}</p>

															<p class="d e" style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:27px;letter-spacing:0;color:#333333;font-size:18px;text-align:center">&nbsp;</p>

															{self._get_headline_html(content.get('headline', ''))}
															
															{self._get_subheadline_html(content.get('subheadline', ''))}
															
															{self._get_bullet_points_html(content.get('bullet_points', []))}

															<p class="d e" style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:27px;letter-spacing:0;color:#333333;font-size:18px;text-align:center">&nbsp;</p>

															<p class="d e" style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:27px;letter-spacing:0;color:#333333;font-size:18px;text-align:center">{content.get('main_content', '')}</p>
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
								<tr>
									<td align="left" style="Margin:0;padding-right:20px;padding-bottom:10px;padding-left:20px;padding-top:10px">
									<table cellpadding="0" cellspacing="0" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
										<tbody>
											<tr>
												<td align="center" style="padding:0;Margin:0;width:560px" valign="top">
												<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:separate;border-spacing:0px;border-left:2px dashed #cccccc;border-right:2px dashed #cccccc;border-top:2px dashed #cccccc;border-bottom:2px dashed #cccccc;border-radius:5px" width="100%">
													<tbody>
														<tr>
															<td align="center" class="k" style="padding:0;Margin:0;padding-top:20px;padding-right:20px;padding-left:20px">
															<h3 class="bh e d" style="Margin:0;font-family:arial, 'helvetica neue', helvetica, sans-serif;mso-line-height-rule:exactly;letter-spacing:0;font-size:18px;font-style:normal;font-weight:bold;line-height:21.6px;color:#333333">🎯 Ready to Take Action?</h3>
															</td>
														</tr>
														<tr>
															<td align="center" class="f br bs" style="Margin:0;padding-right:20px;padding-left:20px;padding-bottom:20px;padding-top:10px">
															<p class="d e" style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:24px;letter-spacing:0;color:#333333;font-size:16px;text-align:center">{content.get('offer_details', "Don't miss out on this incredible opportunity!")}</p>
															</td>
														</tr>
														<tr>
															<td align="center" style="Margin:0;padding-bottom:20px;padding-left:20px;padding-right:20px">
															<a href="{content['cta_url']}" target="_blank" style="display:inline-block;background-color:#00CED1;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-size:16px;font-weight:bold;line-height:1.2;text-align:center;margin:0;">{content['cta_text']}</a>
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
								<tr>
									<td align="left" style="padding:0;Margin:0;padding-right:20px;padding-bottom:10px;padding-left:20px">&nbsp;</td>
								</tr>
							</tbody>
						</table>
						</td>
					</tr>
				</tbody>
			</table>

			<table align="center" cellpadding="0" cellspacing="0" class="t" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;width:100%;table-layout:fixed !important">
				<tbody>
					<tr>
						<td align="center" style="padding:0;Margin:0">
						<table align="center" bgcolor="#f8f9fa" cellpadding="0" cellspacing="0" class="bm footer-bg" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;background-color:#f8f9fa;width:600px;max-width:100%">
							<tbody>
								<tr>
									<td align="center" class="mobile-padding" style="Margin:0;padding-top:30px;padding-right:20px;padding-bottom:30px;padding-left:20px">
									<table cellpadding="0" cellspacing="0" role="none" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
										<tbody>
											<tr>
												<td align="center" style="padding:0;Margin:0;width:560px" valign="top">
												<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px" width="100%">
													<tbody>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0">
															<h3 style="Margin:0;font-family:arial, 'helvetica neue', helvetica, sans-serif;mso-line-height-rule:exactly;letter-spacing:0;font-size:18px;font-style:normal;font-weight:bold;line-height:22px;color:#00CED1">
																KemisEmail – Delivering Local Deals and Offers Since 2005
															</h3>
															</td>
														</tr>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0;padding-top:20px">
															<p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:18px;letter-spacing:0;font-size:12px;font-style:normal;font-weight:normal;color:#666666">
																2026 © Kemis Group of Companies Inc. All rights reserved.
															</p>
															</td>
														</tr>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0;padding-top:10px">
															<p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:18px;letter-spacing:0;font-size:12px;font-style:normal;font-weight:normal;color:#666666">
																Nassau West, New Providence, The Bahamas
															</p>
															</td>
														</tr>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0;padding-top:20px">
															<table cellpadding="0" cellspacing="0" class="footer-links" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;width:100%;margin:0 auto" align="center">
																<tbody>
																	<tr>
																		<td align="center" style="padding:0;Margin:0;padding-right:15px">
																		<a href="https://dzvs3n3sqle.typeform.com/to/JxCYlnLb" style="text-decoration:none;color:#00CED1;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-size:14px;font-weight:normal;">Sign Up</a>
																		</td>
																		<td align="center" style="padding:0;Margin:0;padding-right:15px">
																		<a href="https://kemisdigital.com/policies/refund-policy" style="text-decoration:none;color:#666666;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-size:14px;font-weight:normal;">Privacy Policy</a>
																		</td>
																		<td align="center" style="padding:0;Margin:0">
																		<a href="https://kemisdigital.com/policies/terms-of-service" style="text-decoration:none;color:#666666;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-size:14px;font-weight:normal;">Terms of Use</a>
																		</td>
																	</tr>
																</tbody>
															</table>
															</td>
														</tr>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0;padding-top:20px">
															<p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:18px;letter-spacing:0;font-size:12px;font-style:normal;font-weight:normal;color:#666666">
																You are receiving this because you signed up for our Deals and Offers list.
															</p>
															</td>
														</tr>
														<tr>
															<td align="center" class="bk" style="padding:0;Margin:0;padding-top:10px">
															<p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:18px;letter-spacing:0;font-size:12px;font-style:normal;font-weight:normal;color:#666666">
																Click here to <a href="[unsubscribe]" style="color:#666666;text-decoration:underline;">unsubscribe</a> if this is no longer of interest.
															</p>
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
															<p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:18px;letter-spacing:0;color:#CCCCCC;font-size:12px">No longer want to receive these emails?&nbsp;<a href="[unsubscribe]" style="mso-line-height-rule:exactly;text-decoration:underline;color:#CCCCCC;font-size:12px" target="_blank">Unsubscribe</a>.</p>
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
</html>"""
        
        return html_template
    
    def _get_images_html(self, images, alt_text, cta_url=None):
        """Generate HTML for one or more images stacked vertically
        Images can be either HTTP URLs or base64 data URIs
        """
        if not images or len(images) == 0:
            # No images - show placeholder
            if cta_url:
                return f'<a href="{cta_url}" target="_blank" style="text-decoration: none;"><div style="display: block; font-size: 14px; border: 0px; outline: none; text-decoration: none; border-radius: 15px; width: 560px; height: 400px; background: linear-gradient(135deg, #00CED1 0%, #FFD700 100%); display: flex; align-items: center; justify-content: center; color: white; font-size: 24px; font-weight: bold;">{alt_text}</div></a>'
            else:
                return f'<div style="display: block; font-size: 14px; border: 0px; outline: none; text-decoration: none; border-radius: 15px; width: 560px; height: 400px; background: linear-gradient(135deg, #00CED1 0%, #FFD700 100%); display: flex; align-items: center; justify-content: center; color: white; font-size: 24px; font-weight: bold;">{alt_text}</div>'
        
        html_parts = []
        for idx, image_src in enumerate(images):
            if image_src:
                # image_src can be either a URL (http/https) or base64 data URI
                # Add spacing between images (except for first image)
                spacing = '' if idx == 0 else '<div style="height: 15px;"></div>'
                
                if cta_url:
                    img_html = f'{spacing}<a href="{cta_url}" target="_blank" style="text-decoration: none;"><img alt="{alt_text}" class="adapt-img" src="{image_src}" style="display: block; font-size: 14px; border: 0px; outline: none; text-decoration: none; border-radius: 15px; width: 560px; height: auto;" title="{alt_text}" /></a>'
                else:
                    img_html = f'{spacing}<img alt="{alt_text}" class="adapt-img" src="{image_src}" style="display: block; font-size: 14px; border: 0px; outline: none; text-decoration: none; border-radius: 15px; width: 560px; height: auto;" title="{alt_text}" />'
                html_parts.append(img_html)
        
        return ''.join(html_parts)
    
    def _get_headline_html(self, headline):
        """Generate HTML for headline (h2)"""
        if not headline:
            return ''
        return f'<h2 class="d e" style="Margin:0;mso-line-height-rule:exactly;font-family:arial, \'helvetica neue\', helvetica, sans-serif;line-height:32px;letter-spacing:0;color:#333333;font-size:26px;font-weight:bold;text-align:center;padding-top:10px;padding-bottom:5px">{headline}</h2>'
    
    def _get_subheadline_html(self, subheadline):
        """Generate HTML for subheadline (h3)"""
        if not subheadline:
            return ''
        return f'<h3 class="d e" style="Margin:0;mso-line-height-rule:exactly;font-family:arial, \'helvetica neue\', helvetica, sans-serif;line-height:28px;letter-spacing:0;color:#666666;font-size:20px;font-weight:normal;text-align:center;padding-top:5px;padding-bottom:15px">{subheadline}</h3>'
    
    def _get_bullet_points_html(self, bullet_points):
        """Generate HTML for bullet points list"""
        if not bullet_points:
            return ''
        
        # Ensure bullet_points is a list
        if not isinstance(bullet_points, list):
            return ''
        
        if len(bullet_points) == 0:
            return ''
        
        # Create bullet points with proper email-compatible styling using two-column table
        bullet_html = '<table cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;border-spacing:0px;width:100%;margin:15px auto;max-width:500px">'
        for bullet in bullet_points:
            if bullet:  # Only add non-empty bullets
                bullet_html += f'''
            <tr>
                <td style="padding:8px 0;padding-left:30px;width:20px;vertical-align:top">
                    <span style="color:#00CED1;font-weight:bold;font-size:18px;line-height:24px">•</span>
                </td>
                <td style="padding:8px 0;vertical-align:top">
                    <p class="d e" style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:24px;letter-spacing:0;color:#333333;font-size:16px;text-align:left">
                        {bullet}
                    </p>
                </td>
            </tr>'''
        bullet_html += '</table>'
        return bullet_html

# Initialize the generator
generator = TemplateGenerator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test-lists')
def test_lists():
    return render_template('test_lists.html')

@app.route('/get-sendy-lists', methods=['GET'])
def get_sendy_lists():
    """Fetch available lists from Sendy API"""
    try:
        # Check if API key is set
        if not SENDY_API_KEY:
            print("❌ SENDY_API_KEY is not set")
            return jsonify({
                'success': False,
                'error': 'SENDY_API_KEY environment variable is not set'
            }), 500
        
        sendy_url = "https://kemis.net/sendy/api/lists/get-lists.php"
        
        data = {
            'api_key': SENDY_API_KEY,
            'brand_id': '1',  # Your brand ID
            'include_hidden': 'no'  # Optional: set to 'yes' to include hidden lists
        }
        
        print(f"📋 Fetching lists from Sendy API: {sendy_url}")
        print(f"📋 Request data: api_key={SENDY_API_KEY[:8]}..., brand_id={data['brand_id']}")
        
        # Add headers to match the working campaign creation config
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'KemisEmail/1.0',
            'Accept': '*/*'
        }
        
        response = requests.post(sendy_url, data=data, headers=headers, timeout=10)
        print(f"📋 Sendy lists API response status: {response.status_code}")
        print(f"📋 Response text: {response.text[:500]}")
        
        if response.status_code == 200:
            # Sendy returns lists as an object with keys like list1, list2, etc.
            try:
                lists_obj = response.json()
                print(f"📋 Parsed JSON response, found {len(lists_obj)} list keys")
                
                # Convert the object format to an array
                lists_array = []
                for key, value in lists_obj.items():
                    if isinstance(value, dict) and 'id' in value and 'name' in value:
                        lists_array.append({
                            'id': value['id'],
                            'name': value['name']
                        })
                
                # Filter to only show the allowed lists
                allowed_list_names = [
                    '🔥 Engaged Core – Bahamas (Openers)',
                    'Drewber Team',
                    'LawBey Users',
                    'Bahamas Attorneys',
                    'Clients'
                ]
                
                filtered_lists = [
                    lst for lst in lists_array 
                    if lst['name'] in allowed_list_names
                ]
                
                # If we have filtered lists, return them
                if filtered_lists:
                    print(f"📋 Successfully filtered to {len(filtered_lists)} allowed lists")
                    return jsonify({
                        'success': True,
                        'lists': filtered_lists
                    })
                else:
                    # No lists found in response
                    print(f"⚠️ No lists found in response object")
                    return jsonify({
                        'success': False,
                        'error': 'No lists found in Sendy response',
                        'raw_response': response.text[:500]
                    })
            except json.JSONDecodeError as e:
                print(f"❌ Error parsing Sendy lists response as JSON: {e}")
                print(f"📋 Raw response text: {response.text[:500]}")
                # If not JSON, try parsing as plain text (some Sendy versions return different formats)
                return jsonify({
                    'success': False,
                    'error': f'Failed to parse lists response: {str(e)}',
                    'raw_response': response.text[:500]
                })
            except Exception as e:
                print(f"❌ Unexpected error parsing response: {e}")
                print(f"📋 Raw response text: {response.text[:500]}")
                return jsonify({
                    'success': False,
                    'error': f'Error processing lists: {str(e)}',
                    'raw_response': response.text[:500]
                })
        else:
            error_msg = f'Sendy API returned status {response.status_code}'
            print(f"❌ {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg,
                'raw_response': response.text[:500] if response.text else 'No response body'
            }), response.status_code
            
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Sendy API timeout'
        }), 504
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Could not connect to Sendy'
        }), 503
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error fetching lists: {str(e)}'
        }), 500

def upload_image_to_s3(image_bytes, filename, content_type='image/jpeg'):
    """Upload image to AWS S3 bucket"""
    if not S3_CONFIGURED:
        return None
    
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_S3_REGION
        )
        
        # Upload to S3
        s3_key = f"images/{filename}"
        s3_client.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
            Body=image_bytes,
            ContentType=content_type,
            ACL='public-read'  # Make images publicly accessible
        )
        
        # Generate public URL
        if AWS_S3_BASE_URL:
            public_url = f"{AWS_S3_BASE_URL.rstrip('/')}/{s3_key}"
        else:
            # Fallback to standard S3 URL format
            public_url = f"https://{AWS_S3_BUCKET}.s3.{AWS_S3_REGION}.amazonaws.com/{s3_key}"
        
        print(f"✅ Uploaded image to S3: {s3_key}")
        print(f"🔗 S3 Public URL: {public_url}")
        return public_url
        
    except ClientError as e:
        print(f"❌ AWS S3 ClientError uploading image: {e}")
        return None
    except BotoCoreError as e:
        print(f"❌ AWS BotoCoreError uploading image: {e}")
        return None
    except Exception as e:
        print(f"❌ Error uploading image to S3: {e}")
        return None

@app.route('/images/<filename>')
def serve_image(filename):
    """Serve images from the images folder (fallback for local storage)"""
    try:
        from flask import send_from_directory
        import os
        # Security: prevent directory traversal
        filename = os.path.basename(filename)
        if not os.path.exists(os.path.join('images', filename)):
            return jsonify({'error': 'Image not found'}), 404
        return send_from_directory('images', filename)
    except Exception as e:
        print(f"Error serving image {filename}: {e}")
        return jsonify({'error': str(e)}), 404

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
        image_data2 = None
        image_prompt = None
        image_source = "AI Generated"
        
        if image_option == 'ai':
            # Generate image prompt and image (will be base64)
            image_prompt = generator.generate_image_prompt(content)
            image_data = generator.generate_image(image_prompt)
            image_source = "AI Generated"
            # AI images will be converted to URLs in the saving step below
        elif image_option == 'upload':
            # Use uploaded images (one or two)
            if 'uploadedImage' in request.form:
                image_data = request.form['uploadedImage']
                image_source = "Uploaded"
            else:
                return jsonify({'error': 'No image uploaded'}), 400
            
            # Check for second image (optional)
            if 'uploadedImage2' in request.form:
                image_data2 = request.form['uploadedImage2']
                image_source = "Uploaded (2 images)"
        elif image_option == 'none':
            # No image
            image_source = "None"
        
        # Create campaign name from subject line
        campaign_name = re.sub(r'[^a-zA-Z0-9\s-]', '', content['subject_line'])
        campaign_name = re.sub(r'\s+', '-', campaign_name.strip())
        campaign_name = campaign_name[:50]  # Limit length
        
        # Save template to templates folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Ensure directories exist
        os.makedirs('templates', exist_ok=True)
        os.makedirs('images', exist_ok=True)
        
        # Save images and generate public URLs
        image_urls = []
        for idx, img_data in enumerate([image_data, image_data2] if image_data2 else ([image_data] if image_data else [])):
            if img_data and img_data.startswith('data:image'):
                import base64
                try:
                    # Extract image data from base64
                    image_format = img_data.split(';')[0].split('/')[1]
                    image_data_clean = img_data.split(',')[1]
                    image_bytes = base64.b64decode(image_data_clean)
                    
                    # Generate filename
                    suffix = f"_{idx+1}" if image_data2 else ""
                    image_filename_only = f"{campaign_name}_{timestamp}{suffix}.{image_format}"
                    content_type = f"image/{image_format}"
                    
                    # Try to upload to S3 first (if configured)
                    public_url = None
                    if S3_CONFIGURED:
                        public_url = upload_image_to_s3(image_bytes, image_filename_only, content_type)
                    
                    # Fallback to local storage if S3 upload failed or not configured
                    if not public_url:
                        image_filepath = f"images/{image_filename_only}"
                        os.makedirs('images', exist_ok=True)
                        
                        with open(image_filepath, 'wb') as f:
                            f.write(image_bytes)
                        
                        # Generate public URL (use environment variable or relative path)
                        base_url = os.getenv('BASE_URL', '')
                        if base_url:
                            public_url = f"{base_url.rstrip('/')}/images/{image_filename_only}"
                        else:
                            # Use relative path for local development
                            public_url = f"/images/{image_filename_only}"
                        
                        print(f"💾 Saved image {idx+1} locally: {image_filepath}")
                    
                    if public_url:
                        image_urls.append(public_url)
                        print(f"🔗 Public URL: {public_url}")
                    else:
                        print(f"⚠️ Could not save or upload image {idx+1}")
                        
                except Exception as e:
                    print(f"⚠️ Could not save image {idx+1}: {e}")
        
        # Create HTML template with image URLs (not base64)
        html_template = generator.create_html_template(content, image_urls)
        
        # Save template to templates folder
        template_filename = f"templates/{campaign_name}_{timestamp}.html"
        
        with open(template_filename, 'w', encoding='utf-8') as f:
            f.write(html_template)
        
        filename = template_filename
        
        # Check template size before returning
        html_size = len(html_template.encode('utf-8'))
        print(f"📧 Generated template size: {html_size:,} bytes")
        
        # If template is too large, try to compress it
        if html_size > 800 * 1024:  # 800KB limit for response
            print(f"⚠️ Large template detected: {html_size:,} bytes, compressing...")
            
            # Try to compress by removing large base64 images
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
        
        # Return the image URLs for preview
        return jsonify({
            'success': True,
            'content': content,
            'image_prompt': image_prompt,
            'image_data': image_urls[0] if image_urls else None,  # Return URL instead of base64
            'image_urls': image_urls,  # Return all URLs
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

@app.route('/regenerate-preview', methods=['POST'])
def regenerate_preview():
    """Regenerate HTML template with edited content"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        content = data.get('content', {})
        image_urls = data.get('image_urls', [])
        
        if not content:
            return jsonify({'error': 'Missing content'}), 400
        
        # Regenerate HTML template with updated content
        html_template = generator.create_html_template(content, image_urls)
        
        return jsonify({
            'success': True,
            'html_template': html_template
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/send-test-email', methods=['POST'])
def send_test_email():
    """Send test email directly to specified email address only"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        emails = data.get('emails', '')
        html_template = data.get('html_template', '')
        content = data.get('content', {})
        
        if not emails or not html_template:
            return jsonify({'error': 'Missing emails or HTML template'}), 400
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, emails):
            return jsonify({'error': 'Invalid email address format'}), 400
        
        # Create a test campaign and send immediately to the specific email only
        sendy_url = "https://kemis.net/sendy/api/campaigns/create.php"
        
        # Generate test campaign name
        now = datetime.now()
        test_campaign_name = f"TEST - {content.get('subject_line', 'Test Email')} - {now.strftime('%m-%d-%Y %H:%M')}"
        
        # Create plain text version
        plain_text = f"""
{content.get('subject_line', 'Test Email')}

{content.get('greeting', 'Hello')}

{content.get('main_content', '')}

{content.get('cta_text', '')}
{content.get('cta_url', '')}

{content.get('offer_details', '')}
{content.get('urgency_text', '')}

---
This is a test email from KemisEmail Template Creator.
        """.strip()
        
        # Prepare campaign data for test send - using direct email sending
        test_data = {
            'api_key': SENDY_API_KEY,
            'brand_id': '1',
            'from_name': 'KemisEmail (Test)',
            'from_email': 'offers@kemis.net',
            'reply_to': 'offers@kemis.net',
            'title': test_campaign_name,
            'subject': f"[TEST] {content.get('subject_line', 'Test Email')}",
            'html_text': html_template,
            'plain_text': plain_text,
            'list_ids': '',  # No list IDs for test emails
            'send_campaign': '0',  # Don't send to lists
            'test_email': emails  # Send directly to this email only
        }
        
        # Add headers that work
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'KemisEmail/1.0',
            'Accept': '*/*'
        }
        
        print(f"📧 Creating test campaign for: {emails}")
        print(f"📧 Test campaign name: {test_campaign_name}")
        
        response = requests.post(sendy_url, data=test_data, headers=headers, timeout=30)
        print(f"📧 Test campaign response: {response.status_code} - {response.text[:200]}")
        
        if response.status_code == 200:
            response_text = response.text.strip()
            if 'campaign created' in response_text.lower() or 'sending' in response_text.lower():
                return jsonify({
                    'success': True,
                    'message': f'Test email campaign created and sent to your list. Check your inbox!'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Sendy response: {response_text}'
                })
        else:
            return jsonify({
                'success': False,
                'error': f'Sendy API returned status {response.status_code}'
            }), response.status_code
        
    except Exception as e:
        print(f"❌ Error sending test email: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/test-email')
def test_email_page():
    """Serve the email test page"""
    return render_template('test_email.html')

@app.route('/verify-email-config', methods=['GET'])
def verify_email_config():
    """Check Sendy configuration and connectivity"""
    try:
        config_info = {
            'sendy_url': 'https://kemis.net/sendy/',
            'api_key_masked': f"{SENDY_API_KEY[:8]}...",
            'from_email': 'offers@kemis.net',
            'from_name': 'KemisEmail',
            'reply_to': 'offers@kemis.net',
            'brand_id': '1'
        }
        
        # Test Sendy connectivity
        test_url = "https://kemis.net/sendy/"
        try:
            test_response = requests.get(test_url, timeout=10)
            config_info['sendy_accessible'] = test_response.status_code == 200
            config_info['sendy_status'] = test_response.status_code
        except Exception as e:
            config_info['sendy_accessible'] = False
            config_info['sendy_error'] = str(e)
        
        # Test API key with a simple request
        api_test_url = "https://kemis.net/sendy/api/subscribers.php"
        api_test_data = {
            'api_key': SENDY_API_KEY,
            'list': 'DU0p7BsJdnwE0MXNZusbMQ'
        }
        
        try:
            api_response = requests.post(api_test_url, data=api_test_data, timeout=10)
            config_info['api_key_valid'] = api_response.status_code == 200
            config_info['api_response'] = api_response.text[:200]
        except Exception as e:
            config_info['api_key_valid'] = False
            config_info['api_error'] = str(e)
        
        return jsonify({
            'success': True,
            'config': config_info
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/send-direct-test', methods=['POST'])
def send_direct_test():
    """Send a minimal test email directly via Sendy API"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        test_email = data.get('email', '')
        test_subject = data.get('subject', 'Test Email from KemisEmail')
        test_body = data.get('body', 'This is a test email to verify email delivery.')
        
        if not test_email:
            return jsonify({'error': 'Email address is required'}), 400
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, test_email):
            return jsonify({'error': 'Invalid email address format'}), 400
        
        # Create minimal HTML template
        minimal_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{test_subject}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #00CED1;">🧪 Test Email</h2>
                <p>{test_body}</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 12px; color: #666;">
                    This is a test email from KemisEmail Template Generator.<br>
                    Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                </p>
            </div>
        </body>
        </html>
        """
        
        # Create plain text version
        plain_text = f"""
{test_subject}

{test_body}

---
This is a test email from KemisEmail Template Generator.
Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()
        
        # Generate test campaign name
        now = datetime.now()
        test_campaign_name = f"DIRECT TEST - {now.strftime('%m-%d-%Y %H:%M')}"
        
        # Prepare campaign data for direct test - send only to specified email
        test_data = {
            'api_key': SENDY_API_KEY,
            'brand_id': '1',
            'from_name': 'KemisEmail (Test)',
            'from_email': 'offers@kemis.net',
            'reply_to': 'offers@kemis.net',
            'title': test_campaign_name,
            'subject': f"[TEST] {test_subject}",
            'html_text': minimal_html,
            'plain_text': plain_text,
            'list_ids': '',  # No list IDs for test emails
            'send_campaign': '0',  # Don't send to lists
            'test_email': test_email  # Send directly to this email only
        }
        
        # Add headers that work
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'KemisEmail/1.0',
            'Accept': '*/*'
        }
        
        sendy_url = "https://kemis.net/sendy/api/campaigns/create.php"
        
        print(f"📧 Sending direct test email to: {test_email}")
        print(f"📧 Test campaign: {test_campaign_name}")
        print(f"📧 Subject: {test_subject}")
        
        response = requests.post(sendy_url, data=test_data, headers=headers, timeout=30)
        print(f"📧 Direct test response: {response.status_code} - {response.text[:200]}")
        
        if response.status_code == 200:
            response_text = response.text.strip()
            if 'campaign created' in response_text.lower() or 'sending' in response_text.lower():
                return jsonify({
                    'success': True,
                    'message': f'Direct test email sent successfully! Check {test_email} for delivery.',
                    'campaign_name': test_campaign_name,
                    'sendy_response': response_text
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Sendy response: {response_text}',
                    'sendy_response': response_text
                })
        else:
            return jsonify({
                'success': False,
                'error': f'Sendy API returned status {response.status_code}',
                'response_text': response.text
            }), response.status_code
        
    except Exception as e:
        print(f"❌ Error sending direct test email: {str(e)}")
        return jsonify({'error': str(e)}), 500

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
        list_ids = data.get('list_ids', '')  # Comma-separated list IDs
        send_option = data.get('send_option', 'draft')  # 'draft', 'send_now', or 'schedule'
        scheduled_datetime = data.get('scheduled_datetime', None)  # Unix timestamp
        
        if not content or not html_template:
            return jsonify({'error': 'Missing content or HTML template'}), 400
        
        if not list_ids:
            return jsonify({'error': 'Please select at least one mailing list'}), 400
        
        # Check if HTML template is too large (over 1MB)
        html_size = len(html_template.encode('utf-8'))
        if html_size > 1024 * 1024:  # 1MB
            print(f"📧 Large HTML template detected: {html_size:,} bytes")
            
            # Try to compress by removing large base64 images
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
        result = generator.send_to_sendy(
            content, 
            html_template, 
            filename,
            list_ids=list_ids,
            send_option=send_option,
            scheduled_datetime=scheduled_datetime
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') != 'production'
    
    # Print S3 configuration status
    if S3_CONFIGURED:
        print("✅ AWS S3 configured - images will be uploaded to S3")
        print(f"   Bucket: {AWS_S3_BUCKET}, Region: {AWS_S3_REGION}")
    else:
        print("⚠️ AWS S3 not configured - images will be saved locally")
        print("   Note: On Railway, local files are ephemeral and will be lost on restart")
        print("   To enable S3 uploads, set: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET")
    
    app.run(debug=debug, host='0.0.0.0', port=port) 