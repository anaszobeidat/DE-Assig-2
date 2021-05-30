from datetime import timedelta
from airflow.utils.dates import days_ago

from airflow import DAG

from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import logging

import pandas as pd
import json
import csv

LOGGER = logging.getLogger("airflow.task")

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': [],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}
with DAG(
        'Anas-DE-Assig-2',
        default_args=default_args,
        description='Assig-2',
        schedule_interval=None,
        start_date=days_ago(3),
        tags=['DE-Assig-2'],
) as dag:
    install_deps = BashOperator(
        task_id='install_dependecies',
        bash_command='pip install sqlalchemy matplotlib sklearn'
    )
    def generate_days(**kwargs):
        List_of_days = []
        for year in range(2020, 2022):
            for month in range(1, 13):
                for day in range(1, 32):
                    month = int(month)
                    if day <= 9:
                        day = f'0{day}'
                    if month <= 9:
                        month = f'0{month}'
                    List_of_days.append(f'{month}-{day}-{year}')
        with open('/home/airflow/data/DE-Days.csv', 'w') as f:
            write = csv.writer(f)
            write.writerow(['days'])
            for i in List_of_days:
                LOGGER.info(i)
                write.writerow([i])
            LOGGER.info('days generated')


    generate_days_operator = PythonOperator(
        task_id='generate_days',
        python_callable=generate_days,
        dag=dag
    )

    def Get_DF_i(Day):
        DF_i = pd.DataFrame()
        try:
            URL_Day = f'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_daily_reports/{Day}.csv'
            DF_day = pd.read_csv(URL_Day)
            DF_day['Day'] = Day
            cond = (DF_day.Country_Region == 'United Kingdom')
            Selec_columns = ['Day', 'Country_Region', 'Last_Update',
                         'Lat', 'Long_', 'Confirmed', 'Deaths', 'Recovered', 'Active',
                         'Combined_Key', 'Incident_Rate', 'Case_Fatality_Ratio']
            DF_i = DF_day[cond][Selec_columns].reset_index(drop=True)
        except:
            pass
        return DF_i


    def extract_csv(**kwargs):
        import time
        List_of_days = pd.read_csv('/home/airflow/data/DE-Days.csv')['days']
        Start=time.time()
        DF_all=[]
        for Day in List_of_days:
            LOGGER.info(str(Day))
            DF_all.append(Get_DF_i(Day))
        End=time.time()
        Time_in_sec=round((End-Start)/60,2)
        LOGGER.info(f'It took {Time_in_sec} minutes to get all data')
        DF_UK=pd.concat(DF_all).reset_index(drop=True)
        # Create DateTime for Last_Update
        DF_UK['Last_Update']=pd.to_datetime(DF_UK.Last_Update, infer_datetime_format=True)
        DF_UK['Day']=pd.to_datetime(DF_UK.Day, infer_datetime_format=True)

        DF_UK['Case_Fatality_Ratio']=DF_UK['Case_Fatality_Ratio'].astype(float)
        DF_UK.to_csv('/home/airflow/data/DE-Assig-2.csv')



    generate_initial_data_operator = PythonOperator(
        task_id='extract_UK_csv',
        python_callable=extract_csv,
        dag=dag
    )

    def generate_plot_and_data(**kwargs):
        import matplotlib.pyplot as plt
        import matplotlib
        DF_UK = pd.read_csv('/home/airflow/data/DE-Assig-2.csv')
        font = {'weight' : 'bold',
                'size'   : 18}

        matplotlib.rc('font', **font)

        plt.figure(figsize=(12,8))
        DF_UK_u=DF_UK.copy()
        Selec_Columns=['Confirmed','Deaths', 'Recovered', 'Active', 'Incident_Rate','Case_Fatality_Ratio']
        DF_UK_u_2=DF_UK_u[Selec_Columns]


        from sklearn.preprocessing import MinMaxScaler

        min_max_scaler = MinMaxScaler()


        DF_UK_u_3 = pd.DataFrame(min_max_scaler.fit_transform(DF_UK_u_2[Selec_Columns]),columns=Selec_Columns)
        DF_UK_u_3.index=DF_UK_u_2.index
        DF_UK_u_3['Day']=DF_UK_u.Day
        DF_UK_u_3[Selec_Columns].plot(figsize=(20,10))
        plt.savefig('/home/airflow/data/uk_scoring_report.png')
        DF_UK_u_3.to_csv('/home/airflow/data/uk_scoring_report.csv')

    generate_plot_and_data_operator = PythonOperator(
        task_id='uk_scoring_report.png',
        python_callable=generate_plot_and_data,
        dag=dag
    )

    def to_db(**kwargs):
        from sqlalchemy import create_engine
        from datetime import date

        DF_uk_u_3 = pd.read_csv('/home/airflow/data/uk_scoring_report.csv')
        Day = str(date.today())
        host="postgres"
        database="airflow"
        user="airflow"
        password="airflow"
        port='5432'
        engine = create_engine(f'postgresql://{user}:{password}@{host}:{port}/{database}')
        DF_uk_u_3.to_sql(f'uk_scoring_report_{Day}', engine,if_exists='replace',index=False)

    to_db_operator = PythonOperator(
        task_id='load_to_postgresDB',
        python_callable=to_db,
        dag=dag
    )

    install_deps >> generate_days_operator
    generate_days_operator >> generate_initial_data_operator
    generate_initial_data_operator >> generate_plot_and_data_operator
    generate_plot_and_data_operator >> to_db_operator