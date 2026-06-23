
#include<avr/io.h>
#include<avr/interrupt.h>


// Cấu hình Driver 
#define STEPES_PER_REV_DRIVER 2000
#define LEAD_MM              2.0f
#define STEPS_PER_MM   ((float)STEPES_PER_REV_DRIVER / LEAD_MM)     


// PIN
#define MOTOR_A_STEP_PIN   2
#define MOTOR_A_DIR_PIN    5

#define ENABLE_PIN         8


// Thông số chuyển động
#define DEFAULT_SPEED      8000
#define MIN_SPEED          100
#define MAX_SPEED          35000
#define STEP_PULSE_US      10
#define DIR_SETUP_US       20



// Timer1 - CTC Mode
#define TIMER_TICKS_PER_SEC   (F_CPU / 8UL)   // = 2,000,000

volatile int32_t  isr_steps_remaining = 0;
volatile bool     isr_moving          = false;


//  BIẾN TOÀN CỤC
int32_t  current_pos_steps = 0;
uint16_t speed_steps_sec   = DEFAULT_SPEED;
bool     motor_enabled     = false;

ISR(TIMER1_COMPA_vect) {
    if (isr_steps_remaining <= 0) {
        TCCR1B &= ~((1 << CS12) | (1 << CS11) | (1 << CS10));
        TIMSK1 &= ~(1 << OCIE1A);
        isr_moving = false;
        return;
    }

    // Phát xung STEP HIGH cho motor
    PORTD |=  (1 << 2) ;
    _delay_us(STEP_PULSE_US);
    PORTD &= ~(1 << 2) ;

    isr_steps_remaining--; // giảm số bước còn lại 

    if (isr_steps_remaining <= 0) {
        isr_moving = false;
        TCCR1B &= ~((1 << CS12) | (1 << CS11) | (1 << CS10));
        TIMSK1 &= ~(1 << OCIE1A);
    }
}


// Khởi động TIMER1
void start_timer1 ( uint16_t freq_hz){
  uint32_t ocr = ( TIMER_TICKS_PER_SEC / freq_hz) - 1;  // tính tần số cấp xung timer đếm từ 0 -> ocr xong ngắt và thực hiện ngắt
  if ( ocr > 65535) ocr = 65535 ; 

  cli() ; // Clear Itr ngắt toàn bộ interrupt để cấu hình tránh ngắt khác xen vào
  TCCR1A = 0;
  TCCR1B = 0;
  TCNT1  = 0;
  OCR1A  = (uint16_t)ocr;
  TCCR1B |= (1 << WGM12);
  TCCR1B |= (1 << CS11);
  TIMSK1 |= (1 << OCIE1A);
  sei(); // Set ITR : mở lại TImer
}

// Dừng TIMER1
void stop_timer1() {
    cli();
    TCCR1B &= ~((1 << CS12) | (1 << CS11) | (1 << CS10));
    TIMSK1 &= ~(1 << OCIE1A);
    isr_moving          = false;
    isr_steps_remaining = 0;
    sei();
}


// Bật / tắt Driver 
void enable_motors() {
    digitalWrite(ENABLE_PIN, HIGH);
    motor_enabled = true;
    delay(5);
}

void disable_motors() {
    digitalWrite(ENABLE_PIN, LOW);
    motor_enabled = false;
}


// Di chuyển động cơ theo bước + ACK
void move_steps( int32_t steps , bool send_ack = false){
    if ( steps == 0 ){
      if ( send_ack){
        Serial.println(F("OK"));
      }
      return ; 
    }

    while ( isr_moving) {};  // chờ nếu đang chạy lệnh cũ / tránh gọi chồng lên nhau

    bool    positive  = (steps > 0);
    int32_t abs_steps = positive ? steps : -steps;

    digitalWrite(MOTOR_A_DIR_PIN, positive ? HIGH : LOW);
    delayMicroseconds(DIR_SETUP_US);

    enable_motors();

    cli();
    isr_steps_remaining = abs_steps ; 
    isr_moving = true ; 
    sei();
    start_timer1(speed_steps_sec);

    while(isr_moving){}

    Serial.print(F("Moved: ")) ; 
    Serial.print(steps);
    Serial.println(F("b")) ;    

    if (send_ack){
      Serial.println(F("OK"));
    }
}



// Di chuyển động cơ theo mm  để test dùng terminal thủ công
void move_mm( float mm){
  int32_t steps = (int32_t)(mm * STEPS_PER_MM);
  if ( steps ==0){
    return ; 
  }

  move_steps( steps, false);
}



void process_command( char* cmd){
  while ( *cmd ==' ') cmd ++ ; // bỏ khoảng trắng ở đầu 
  if(strlen(cmd) ==0 ) return ; 

  /// xử lý các kỉ tự
  // 1. Enable / Disable Driver
  if (strcmp(cmd, "e") ==0 || strcmp(cmd, "E") ==0){
    enable_motors();
    Serial.println(F("Driver: ON"));
    return ; 
  }
  if (strcmp(cmd, "d") ==0 || strcmp(cmd, "D") ==0){
    disable_motors();
    Serial.println(F("Driver: OFF"));
    return ; 
  }

  //2. dừng khẩn cấp 
  if (strcmp(cmd, "x") == 0 || strcmp(cmd, "X") == 0) {
      stop_timer1();
      Serial.println(F("DUNG KHAN CAP"));
      return;
  }


  // 3. Set tốc độ cho động cơ 
  if (cmd[0] == 's' || cmd[0] == 'S') {
      int32_t spd = atol(cmd + 1);
      if (spd <= 0) { Serial.println(F("Loi: toc do phai > 0")); return; }
      if (spd < MIN_SPEED) spd = MIN_SPEED;
      if (spd > MAX_SPEED) spd = MAX_SPEED;
      speed_steps_sec = (uint16_t)spd;
      Serial.print(F("Toc do: "));
      Serial.print(speed_steps_sec);

      return;
  }


  // 4. di chuyển theo bước với định dạng <n>b 
  uint8_t len= strlen(cmd);
  if ( cmd[len-1] =='b' || cmd[len-1] =='B'){
    cmd[len-1] = '\0';
    int32_t steps = atol(cmd);

    if (steps ==0){
      Serial.println(F("Loi: so buoc khong hop le!"));
      Serial.println(F("OK"));
      return ; 
    }
    move_steps(steps, true);
    return ; 
  }

  // 5. di chuyển theo mm 
  float mm = atof(cmd);
  if ( mm == 0.0f && cmd[0] != '0' && cmd[0] != '-'){
    Serial.println(F("Loi: lenh khong hop le"));
    return ; 
  }
  move_mm(mm);
}

// ════════════════════════════════════════════════════════════
//  BUFFER SERIAL
// ════════════════════════════════════════════════════════════

#define LINE_BUF_SIZE 32
char    line_buf[LINE_BUF_SIZE];
uint8_t line_len = 0;


void setup() {
    Serial.begin(115200);

    pinMode(MOTOR_A_STEP_PIN, OUTPUT);
    pinMode(MOTOR_A_DIR_PIN,  OUTPUT);
  
    pinMode(ENABLE_PIN,       OUTPUT);

    digitalWrite(MOTOR_A_STEP_PIN, LOW);
    digitalWrite(MOTOR_A_DIR_PIN,  LOW);

    disable_motors();

    delay(100);

    Serial.println(F("San sang nhan lenh (ACK handshake BAT):"));

}

void loop() {
    while (Serial.available()) {
        char c = Serial.read();

        if (c == '\n') {
            // Kết thúc dòng → xử lý
            if (line_len > 0) {
                line_buf[line_len] = '\0';
                process_command(line_buf);
                line_len = 0;
            }
        }
        else if (c == '\r') {
            // Bỏ qua ký tự CR (Windows "\r\n")
            // Không reset line_len ở đây, chờ '\n'
        }
        else if (c == 8 || c == 127) {
            // Backspace
            if (line_len > 0) line_len--;
        }
        else if (line_len < LINE_BUF_SIZE - 1) {
            line_buf[line_len++] = c;
        }
    }
}
