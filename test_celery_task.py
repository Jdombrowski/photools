from src.workers.photo_processor import process_single_photo 
import os                                                    
print('Testing Celery task execution...')                    
                                                             
# Create a simple test file                                  
test_file = '/tmp/test.txt'                                  
with open(test_file, 'w') as f:                              
    f.write('test content')                                  
                                                             
# Send a test task to Celery                                 
result = process_single_photo(test_file, '/tmp/test.txt')               
print(f'Task sent with ID: {result.id}')                     
print(f'Task state: {result.state}')                         
                                                             
# Cleanup                                                    
os.remove(test_file)                                         
print('Test completed successfully!')                        
 